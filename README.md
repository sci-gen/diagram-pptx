# diagram-pptx

**Mermaid in. Editable PowerPoint shapes out.**

[![Python 3.10–3.13](https://img.shields.io/badge/python-3.10%E2%80%933.13-3776AB.svg)](https://www.python.org/)
[![MIT License](https://img.shields.io/badge/license-MIT-2EA44F.svg)](LICENSE)
[![Package status](https://img.shields.io/badge/status-alpha-F59E0B.svg)](#status)
[![Native PowerPoint](https://img.shields.io/badge/output-editable%20PPTX-CC2927.svg)](#why-this-is-not-an-svg-converter)

`diagram-pptx` is a Python-native diagram object model and compiler that turns
Mermaid into editable PowerPoint AutoShapes, connectors, text, and groups. It
works directly with `python-pptx`, so generated diagrams can share a slide
with ordinary presentation content and remain addressable from Python.

![Flowchart and sequence diagram composed on one editable slide](https://raw.githubusercontent.com/sci-gen/diagram-pptx/main/docs/assets/readme/same-slide-composition.png)

The screenshot above was generated from two independent Mermaid sources on
one slide. The PPTX contains two editable groups and no full-diagram image.

## Fastest path

Native rendering requires no PowerPoint, Node.js, Chromium, Docker, or
LibreOffice:

```bash
pip install diagram-pptx
diagram-pptx render diagram.mmd diagram.pptx
```

For the current source checkout before the first PyPI release:

```bash
python -m pip install -e .
diagram-pptx render examples/flowchart.mmd diagram.pptx
```

Or create the same editable output inside an existing `python-pptx`
presentation:

```python
from pptx import Presentation
from diagram_pptx import render_mermaid

prs = Presentation()
slide = prs.slides.add_slide(prs.slide_layouts[6])

render_mermaid(
    "flowchart LR\n  request[Request] --> check{Valid?}\n"
    "  check -->|yes| done[Done]\n  check -->|no| request",
    slide=slide,
    position="full",
)

prs.save("diagram.pptx")
```

The result is one movable, resizable, and ungroupable PowerPoint group.

## Highlights

| | |
| --- | --- |
| **Five typed diagram models** | Flowchart, Sequence, Class, ER, and State |
| **PowerPoint-native output** | AutoShapes, connectors, text, and groups—not a screenshot |
| **Python-first editing** | Parse, query, mutate, theme, and compile like an ORM entity graph |
| **Two geometry backends** | Deterministic Pure Python Native or Mermaid CLI Official |
| **Presentation composition** | Place diagrams left/right/top/bottom or at normalized coordinates |
| **Reusable visual systems** | Themes, semantic roles, class/ID overrides, and continuous color maps |
| **Agent-ready boundary** | Typed API plus documented MCP, Codex plugin, and skill adapters |

Mermaid is the primary declarative frontend—not the package's core
representation:

```text
Mermaid / JSON / future frontend
              ↓
      typed semantic model
              ↓
            layout
              ↓
         DrawingScene
              ↓
        style resolution
              ↓
     native python-pptx shapes
```

The generated slide contains AutoShapes, connectors, text boxes, and one
editable PowerPoint group. It does not flatten the entire diagram into an
image.

<table>
  <tr>
    <td width="62%">
      <img alt="Complex native sequence diagram" src="https://raw.githubusercontent.com/sci-gen/diagram-pptx/main/docs/assets/readme/complex-sequence.png">
    </td>
    <td width="38%">
      <img alt="Color maps and automatic text contrast" src="https://raw.githubusercontent.com/sci-gen/diagram-pptx/main/docs/assets/readme/colormap-auto-contrast.png">
    </td>
  </tr>
  <tr>
    <td align="center"><strong>Complex Native layout</strong></td>
    <td align="center"><strong>Color maps + automatic contrast</strong></td>
  </tr>
</table>

> **Status:** `0.1.0a1` is an alpha API. PowerPoint itself is not part of the
> automated test environment; OOXML structure and LibreOffice rendering are
> the compatibility baseline.

## Install

```bash
pip install diagram-pptx
```

The Pure Python Native backend needs only Python, `networkx`, and
`python-pptx`. The Official backend optionally invokes external
`@mermaid-js/mermaid-cli`; the project Docker image pins version `11.16.0`.

`python-pptx` remains a separate distribution and import. It is declared as a
normal dependency because every renderer returns native `python-pptx` objects;
it is not bundled or vendored into `diagram-pptx`. If a compatible
`python-pptx>=1.0.2,<2` is already installed, `pip install diagram-pptx`
reuses that installation.

```python
from pptx import Presentation
from diagram_pptx import render_mermaid
```

## Python API

Parse once, edit the typed model like an ORM entity graph, then compile it:

```python
from pptx import Presentation
from diagram_pptx import parse_mermaid, compile_diagram

source = """
flowchart LR
    api([API]) --> db[(Database)]
"""

document = parse_mermaid(source)
document.model.nodes["db"].label = "Primary DB"
document.model.nodes["db"].classes.add("storage")

prs = Presentation()
slide = prs.slides.add_slide(prs.slide_layouts[6])
result = compile_diagram(
    document,
    slide=slide,
    bounds=(1, 1, 11, 5.5),
    group=True,
)
# Native python-pptx objects remain addressable after grouping.
result.element_shapes["db"].text = "Primary database"
result.group_shape.width = int(result.group_shape.width * 1.1)
prs.save("diagram.pptx")
```

`render_mermaid()` remains the one-call convenience API:

```python
from diagram_pptx import render_mermaid

result = render_mermaid(
    source,
    slide=slide,
    position="left",
    style="official",
    theme={"ids": {"db": {"fill": "accent1"}}},
    group=True,
    strict=False,
)
```

The target is an existing `python-pptx` slide, so multiple diagrams and
ordinary slide content can be composed on the same slide. Placement can use a
named region:

```python
render_mermaid(left_source, slide=slide, position="left")
render_mermaid(right_source, slide=slide, position="right")
```

The presets are `full`, `left`, `right`, `top`, and `bottom`. For arbitrary
slide-relative placement, use normalized `(x, y, width, height)` coordinates
with the top-left corner as `(0, 0)`:

```python
render_mermaid(
    source,
    slide=slide,
    relative_bounds=(0.05, 0.12, 0.40, 0.76),
)
```

For exact physical placement, `bounds=(left, top, width, height)` remains
available in inches. `bounds`, `position`, and `relative_bounds` are mutually
exclusive. If none is supplied, `position="full"` is used.

The layout engine first determines the diagram's logical size. The renderer
then scales it uniformly by
`min(target_width / scene_width, target_height / scene_height)`, centers it in
the target region, and preserves its aspect ratio. Consequently, the target
region determines the maximum diagram size; unused space can remain on one
axis. The returned PowerPoint group can still be moved or resized afterward.

The typed roots are `FlowDiagram`, `SequenceDiagram`, `ClassDiagram`,
`EntityRelationshipDiagram`, and `StateDiagram`. ID-bearing collections are
in insertion-ordered dictionaries, and all roots provide
`select(role=..., class_=...)`. Models and themes support `to_dict()` /
`from_dict()` with `schema_version: 1`; JSON Schemas ship in
`diagram_pptx/schemas`.

## Themes and color maps

Themes can be Python dictionaries, `DiagramTheme` instances, or versioned JSON:

```json
{
  "schema_version": 1,
  "palette": {
    "brand": "#0057B8",
    "surface": "#F6F8FA"
  },
  "roles": {
    "node.default": {
      "fill": "surface",
      "line": "brand",
      "text": "text1"
    }
  },
  "classes": {
    "storage": {
      "fill": "brand",
      "text": "#FFFFFF"
    }
  },
  "ids": {
    "critical": {
      "line_width": 2.5
    }
  },
  "color_map": {
    "#FF0000": "#0057B8"
  }
}
```

With the default `source_style="merge"`, precedence is:

```text
renderer defaults
< theme role defaults
< Mermaid classDef / inline style
< theme class and ID overrides
< render-time element override
< color_map final replacement
```

`preserve` gives explicit Mermaid visual styles final priority. `replace`
ignores Mermaid visual values while retaining semantic roles and class names.
Colors accept RGB, RGBA, palette tokens, and PowerPoint theme slots such as
`accent1` and `text1`.

The layout backend and visual style are independent. Native is the default
backend, while `style="official"` applies a Mermaid-like visual preset without
starting Node, Chromium, or `mmdc`:

```python
render_mermaid(
    source,
    slide=slide,
    bounds=(1, 1, 11, 5.5),
    style="official",
)
```

Named continuous color maps can drive each visual channel from a numeric
position between `0` and `1`:

```python
render_mermaid(
    source,
    slide=slide,
    bounds=(1, 1, 11, 5.5),
    style="official",
    colors={
        "name": "jet",
        "fill": 0.65,
        "line": 0.90,
        "edge": 0.78,
        "text": 0.20,
        "decision_fill": 0.45,
    },
)
```

Built-in maps are `jet`, `viridis`, `plasma`, and `magma`. `fill` colors
ordinary node bodies, `decision_fill` colors decision nodes, `line` colors
node outlines, `edge` colors connectors, and `text` colors labels. For reusable
configuration, pass a `ColorMapStyle` instance instead of a map name.

For a simpler two-color composition, use `primary` and `secondary`:

```python
render_mermaid(
    source,
    slide=slide,
    bounds=(1, 1, 11, 5.5),
    colors={
        "name": "viridis",
        "primary": 0.82,  # ordinary node fill
        "secondary": 0.18,  # decision fill, outlines, connectors, containers
    },
)
```

When `text` is omitted, each filled node independently chooses white or dark
text using relative luminance and the higher WCAG contrast ratio. An explicit
numeric `text` position always wins.

## Tool integrations

The core package is tool-provider neutral. It does not ship OpenAI-, Anthropic-,
or other vendor-specific function wrappers. MCP servers, Codex plugins, and
other agent adapters should live in separate integration packages and call the
same typed Python API.

The public signature uses constrained literal types and the distribution
includes a `py.typed` marker. `CompileResult.to_dict()` returns a compact
JSON-safe operation summary for adapters, while all native `python-pptx`
objects remain available on the result itself.

The MCP SDK can derive its input schema directly from a typed adapter
signature, so the core does not maintain a provider-format schema generator.
See [MCP and Codex integration](docs/mcp-integration.md) for a working FastMCP
server pattern, direct Codex registration, a plugin manifest, and a skill
example.

The pre-alpha flat color arguments remain accepted for compatibility, but new
code should use the JSON-friendly `colors` object.

## Backends

| Backend | Runtime | Behavior |
| --- | --- | --- |
| `native` (default) | Python only | Deterministic Pure Python layout for all five model types |
| `official` | `mmdc` + Chromium | Mermaid computes geometry; Mermaid-specific SVG is imported as editable shapes |
| `auto` | automatic | Uses Official when `mmdc` is available, otherwise Native |

Native flow/state/class/ER connectors bind to verified PowerPoint connection
sites when the target preset has a stable site map. Official paths keep
Mermaid's coordinates instead of being rebound to a different PowerPoint site;
marker margins are extended to the target boundary before rendering.

Node labels are stored in the node AutoShape's own text frame for Native
output and for simple Official flow/state nodes. Connector labels, sequence
message labels, and structured class/ER compartments remain independent text
boxes because a connector or compartment is not a single text-owning
AutoShape.

Default font sizes are fitted with the diagram rather than left at a fixed
slide size. Native starts from 15 pt for nodes, 12 pt for free text, and 11 pt
for edge labels, multiplies by the scene-to-bounds fit scale, and clamps the
result by role. Official converts Mermaid's SVG/CSS pixel geometry through the
same fit transform (`px × inches-per-px × 72`) before applying the role clamp.
An explicit theme `font_size` replaces the role's base size before fitting.

If unsupported Mermaid syntax is encountered, it is preserved in
`MermaidDocument.raw_statements` with line/column diagnostics. An unchanged
partial document can be rendered faithfully by Official. Mutating its partial
semantic structure raises `PartialModelMutationError`, preventing silent data
loss. `strict=True` rejects unsupported syntax at parse time. Applying only a
theme is not a structural mutation.

An external `mmdc` outside the tested `11.16.x` series produces a warning, or
an error in strict mode.

## Mermaid support matrix

| Family | Native semantic coverage in `0.1.0a1` |
| --- | --- |
| Flowchart | directions, common node shapes, labeled/chained edges, cycles, self-loops, nested subgraphs, `classDef`, `class`, `style`, `linkStyle` |
| Sequence | participant/grouped stick actor, sync/async/dashed/lost messages, notes, duration-aware nested activation, autonumber, loop/alt/else/opt/par/critical/break |
| Class | attributes, methods, stereotypes, visual namespace containers, inheritance, realization, aggregation, composition, dependency, labels, notes, direction |
| ER | entity attributes, PK/FK/UK, Mermaid cardinality tokens, relationship labels, direction |
| State | start/end, simple/composite state, boundary-bound transition, hierarchical composite groups, note, direction, choice/fork/join |

Native Sequence actors and composite states, plus Official Sequence stick
figures and multi-part State final markers, are emitted as nested editable
PowerPoint groups. Their component shapes therefore move as one semantic
object. Flow subgraphs and Class namespaces remain visual containers rather
than nested groups. Gantt, mindmap, pie, generic SVG conversion, and
pixel-perfect reproduction remain outside this alpha. Unsupported statements
remain available to the Official backend rather than disappearing.

## Alpha limitations

The five diagram families are usable, but `0.1.0a1` is not complete Mermaid
fidelity:

- Official geometry is imported as editable PowerPoint primitives, but browser
  font metrics and complex Bezier paths can differ slightly.
- Flow subgraphs and Class namespaces are visual containers, not nested
  PowerPoint groups.
- Mermaid families outside the five listed above require a future frontend and
  semantic model. Unsupported statements are diagnosed rather than silently
  dropped.
- Automated compatibility uses OOXML inspection and LibreOffice rendering.
  The generated files have also been opened and inspected manually in
  Microsoft PowerPoint, but that application is not yet part of CI.

## CLI

```bash
diagram-pptx render input.mmd output.pptx \
  --style official --colormap viridis \
  --primary 0.82 --secondary 0.18 --position left --group

diagram-pptx render input.mmd output.pptx \
  --relative-bounds 0.05,0.12,0.40,0.76

diagram-pptx inspect input.mmd --json
diagram-pptx doctor
```

`inspect` reports the family, approximate modeled rate, diagnostics, preserved
statements, and required backend. `doctor` checks Python, `python-pptx`,
Mermaid CLI/version, LibreOffice, and Poppler.

## Docker development and visual review

No local PowerPoint installation is required:

```bash
docker compose run --build --rm test
docker compose run --build --rm official-test
docker compose run --build --rm example
```

The example produces Native and Official five-slide galleries, converts them
to PDF with LibreOffice, rasterizes every slide to PNG with Poppler, and checks
both against fixed-container golden images with a broad structural tolerance.

## Why this is not an SVG converter

The public value is the typed semantic model plus direct `python-pptx`
integration. Python code can query and mutate diagram entities before
compilation, themes can operate on semantic roles/classes/IDs, and the
renderer consumes a backend-neutral `DrawingScene`. The Official backend uses
SVG only as a Mermaid geometry contract; it is deliberately not a general SVG
conversion library.

See [architecture.md](docs/architecture.md) for extension contracts and
[CONTRIBUTING.md](CONTRIBUTING.md) for development checks.

## License

MIT
