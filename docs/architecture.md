# Architecture

## Compiler pipeline

The package boundary is:

```text
parse → semantic model → layout → DrawingScene → style resolution
                                                     ├─ python-pptx
                                                     ├─ SVG
                                                     └─ PNG/JPEG
```

Each stage has one responsibility:

1. A frontend parses source text with source locations and diagnostics.
2. A typed, mutable semantic model represents diagram meaning.
3. A layout backend chooses geometry.
4. `DrawingScene` stores positioned shapes, connectors, text, containers,
   z-order, and semantic IDs.
5. `StyleResolver` applies theme precedence and final color mapping.
6. `PythonPptxRenderer` knows OOXML and emits editable native slide objects;
   `SvgRenderer` emits self-contained vector output, which the optional image
   runtime can rasterize as PNG or JPEG.

Renderers never read Mermaid syntax or a semantic model. Frontends and layout
engines never import PowerPoint enums or XML helpers. `build_scene()` is the
shared public boundary; it selects geometry and resolves all styles before any
output-format-specific code runs.

`python-pptx` is an external runtime dependency rather than vendored code.
Callers create or reuse their own `Presentation` and slide, then
`diagram-pptx` adds editable native objects to that slide. A compatible
preinstalled `python-pptx` is reused by normal package installation.

## Semantic roots

The five typed roots intentionally remain distinct:

- `FlowDiagram`: nodes, edges, nested visual groups
- `SequenceDiagram`: participants and ordered events/fragments
- `ClassDiagram`: classes, compartments, notes, typed relationships
- `EntityRelationshipDiagram`: entities, attributes, keys, cardinalities
- `StateDiagram`: states, composites, pseudostates, transitions

`MermaidSourceDiagram` is a separate lossless root for every other Mermaid
11.16 family. It stores the complete mutable source and explicitly requires
the Official backend; it does not pretend to provide an ORM-like semantic
model or a Native layout.

Forcing these into a single graph type would erase useful constraints. Shared
behavior lives in style primitives, selection helpers, serialization, and the
DrawingScene layer.

ID-bearing entities are mutable dataclasses and stored in insertion-ordered
dictionaries. This makes application code straightforward:

```python
document.model.nodes["db"].label = "Primary DB"
document.model.select(class_="storage")
```

## Native and Official layout

Native is deterministic and has no Node dependency. Flow and State share the
layered graph engine; Class and ER add compartment-aware sizing; Sequence uses
participant columns and event rows.

Official invokes `mmdc` without a shell, with a timeout, isolated temporary
files, captured stderr, version checks, and error-SVG detection. Its SVG
importer accepts only Mermaid's visible geometry contract and ignores scripts,
images, links, and external references. Imported colors still pass through the
same StyleResolver and color map as Native output.

Native is the public default so an installed `mmdc` never changes geometry
implicitly. `official` requests Mermaid geometry explicitly, while `auto`
retains the opt-in runtime-detection behavior. Backend selection is independent
from visual presets such as `style="official"`.

Named continuous color maps are sampled after normal style resolution. Numeric
positions independently control node fill, decision fill, node outline,
connector, text, and container channels, so they override both Native and
Official source colors consistently.

`primary` and `secondary` are shorthand channels: primary supplies ordinary
node fill, while secondary supplies decision fill, outlines, connectors, and
container lines. If no text position is supplied, filled shapes choose white
or dark text independently by relative luminance and contrast ratio.

## Partial-model safety

Every `MermaidDocument` stores:

- original source
- typed model
- diagnostics and raw unsupported statements
- modeled status/rate
- initial semantic fingerprint

Official can compile an unchanged partial document from its original source.
If Python code changes that partial semantic model, compilation fails with
`PartialModelMutationError`; otherwise a serializer would necessarily discard
the unknown statements. Themes do not alter the fingerprint.

## PowerPoint grouping

The renderer creates backgrounds, connectors, nodes, labels, and notes in
z-order, then moves them into one top-level `GroupShape` by default. Child
shape proxies remain available through `CompileResult.element_shapes` and
`element_parts`.

Compilation targets an existing `python-pptx` slide. A caller may therefore
compile multiple independent diagrams into the same slide. Placement is
resolved before rendering from exactly one of:

- physical inch bounds `(left, top, width, height)`
- a `full`, `left`, `right`, `top`, or `bottom` slide-relative preset
- normalized slide-relative bounds `(x, y, width, height)` in the `0..1` range

Normalized coordinates use the slide's top-left as the origin and are
converted from the actual presentation dimensions. The scene is uniformly
scaled to contain within the resolved bounds, centered on the unused axis, and
kept editable as a PowerPoint group. Layout geometry therefore defines the
aspect ratio while the placement bounds define the maximum rendered size.

## API and integration boundary

Human-facing and tool-facing adapters share the same `render_mermaid` entry
point. Known choices use literal types, related continuous color channels live
in one `ColorMapStyle`/`colors` object, and physical versus normalized
placement remains represented by separately named arguments to avoid unit
ambiguity.

The core deliberately contains no vendor-specific function-tool wrappers.
MCP servers, Codex plugins, and other agent adapters are separate integration
layers. They bind a current `python-pptx` slide, invoke the typed API, and can
return `CompileResult.to_dict()` or `ExportResult.to_dict()` as a JSON-safe
summary.

The tool's input schema belongs to the adapter and should be derived from its
typed MCP handler rather than emitted by the core package. Operational
instructions belong to an agent skill. See
[MCP and Codex integration](mcp-integration.md) for the complete boundary and
examples.

The group and children are named with diagram family, semantic role, and
semantic ID. Native Sequence actors and composite states, Official Sequence
stick figures, and multi-part State final markers form nested editable groups
inside the diagram group. Composite-state groups can themselves be nested;
Flow subgraphs and Class namespaces remain visual containers.

Curves unsupported by editable PowerPoint connectors are approximated by
straight connector segments. Fonts and Bezier control points may differ
slightly from Mermaid's browser rendering.

Native graph connectors use a verified preset-specific PowerPoint connection
site map; unsupported custom geometries retain their explicit boundary
coordinates. Official SVG routes are not rebound because doing so would change
Mermaid's geometry. Their marker-offset endpoints are snapped to the target
boundary instead.

Native node labels, and simple Official Flow/State node labels, live in the
node AutoShape's own text frame. Edge labels and structured compartment text
remain separate text boxes. Font and stroke metrics are fitted alongside scene
geometry: inch-based Native metrics use the layout fit scale, while SVG pixel
metrics use the SVG-to-inch scale converted to points. Role-specific clamps
prevent unusably small or oversized text.

## Extending the package

A new declarative syntax should:

1. Parse into an existing typed semantic root, or add a new sibling root when
   its semantics differ.
2. Provide `to_dict()` / `from_dict()` and a versioned schema update.
3. Add a layout adapter that returns `DrawingScene`.
4. Reuse StyleResolver and the existing output renderers unchanged.

A new geometry backend accepts a semantic model and returns `DrawingScene`.
General SVG conversion does not belong in the Mermaid-specific importer.

SVG serialization is dependency-free. PNG and JPEG are optional because they
need the `resvg_py` raster runtime; JPEG additionally flattens alpha through
Pillow. The `image` extra installs these dependencies, while `all` aggregates
all optional runtime features without development tooling. Native image export
does not require Node.js. Official geometry still requires the separately
installed Mermaid CLI and its Node.js/Chromium runtime.

## Compatibility target

- Python 3.10–3.13
- `python-pptx` 1.x
- Mermaid CLI 11.16.x for tested Official geometry
- LibreOffice/OOXML as the automated rendering baseline

Microsoft PowerPoint display identity and pixel-perfect browser equivalence
are not guaranteed by `0.1.0b3`.
