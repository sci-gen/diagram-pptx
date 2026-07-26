<div align="right">
  <strong>English</strong> · <a href="./user-guide.ja.md">日本語</a>
</div>

# diagram-pptx user guide

This guide contains the operational details intentionally kept out of the
project README.

## Contents

- [Python object model](#python-object-model)
- [PowerPoint rendering](#powerpoint-rendering)
- [Image export](#image-export)
- [Placement](#placement)
- [Backends and Node.js](#backends-and-nodejs)
- [Themes and color maps](#themes-and-color-maps)
- [Mermaid support](#mermaid-support)
- [CLI](#cli)
- [Development environment](#development-environment)

## Python object model

`parse_mermaid()` returns a `MermaidDocument` containing the original source,
a typed mutable model, diagnostics, preserved statements, and a fingerprint of
the initial model.

```python
from diagram_pptx import compile_diagram, parse_mermaid
from pptx import Presentation

source = """
flowchart LR
    api([API]) --> db[(Database)]
"""
```

<p align="center">
  <img
    src="./assets/readme/api-database-flow.png"
    alt="API connected to a database, rendered by diagram-pptx"
    width="640"
  >
</p>

The image above is Native output generated directly from that Mermaid source.
The model can then be edited and compiled into an existing slide:

```python
document = parse_mermaid(source)
document.model.nodes["db"].label = "Primary DB"
document.model.nodes["db"].classes.add("storage")

prs = Presentation()
slide = prs.slides.add_slide(prs.slide_layouts[6])

result = compile_diagram(
    document,
    slide=slide,
    bounds=(1, 1, 11, 5.5),
    style="official",
    group=True,
)

result.element_shapes["db"].text = "Primary database"
result.group_shape.width = int(result.group_shape.width * 1.1)
prs.save("database-flow.pptx")
```

ID-bearing semantic entities are mutable dataclasses stored in insertion-
ordered dictionaries. Models and themes support `to_dict()` and `from_dict()`.
The versioned JSON Schema is included in the package.

## PowerPoint rendering

`render_mermaid()` is the concise parse-and-compile API. `compile_diagram()`
accepts a previously parsed document when Python needs to inspect or modify the
semantic model first.

By default, the renderer creates one top-level PowerPoint group containing
editable native shapes, connectors, labels, and annotations. Use
`group=False` to leave all generated shapes at the slide level.

`CompileResult` provides:

- `backend_used` and `mermaid_version`;
- `diagnostics`;
- `group_shape`;
- `element_shapes`, keyed by semantic ID;
- `top_level_shapes`.

PowerPoint itself is not required to create the `.pptx` file. The core runtime
uses `python-pptx`.

## Image export

SVG export has no optional runtime dependency. PNG and JPEG use the `image`
extra:

```bash
pip install "diagram-pptx[image]"
```

Install every optional Python feature with:

```bash
pip install "diagram-pptx[all]"
```

The parsed document supports a Matplotlib-like save API:

```python
document.save("diagram.svg")
document.save("diagram.png", dpi=600, background="transparent")
document.save("diagram.jpg", dpi=300, background="#FFFFFF", quality=92)

svg_text = document.to_svg()
png_bytes = document.to_png(dpi=300)
jpeg_bytes = document.to_jpeg(dpi=300)
```

PNG supports transparent backgrounds. JPEG flattens transparency onto the
requested background. `width_px` and `height_px` request exact raster
dimensions, and a pixel limit prevents accidental extremely large exports.

Image exports use white connector/message-label backgrounds by default. They
can instead use the same fill as a non-white canvas:

```python
canvas = "#0F172A"
document.save(
    "diagram.png",
    background=canvas,
    label_background=canvas,
)
```

The same option works for editable PowerPoint output:

```python
render_mermaid(
    source,
    slide=slide,
    label_background="#F3F0E8",
)
```

Use `label_background="transparent"` to remove the label box. Theme authors
can still set `label_fill` per role, class, or ID; an explicit per-element
override and the color-map `label_fill` channel take precedence over this
global convenience value. For an opaque RGB/RGBA label background, the label
text automatically selects light or dark contrast unless an element override
or color-map `text` channel supplies a color.

## Placement

Render into named regions:

```python
render_mermaid(left_source, slide=slide, position="left")
render_mermaid(right_source, slide=slide, position="right")
```

Or use normalized coordinates measured from the slide's top-left corner:

```python
render_mermaid(
    source,
    slide=slide,
    relative_bounds=(0.05, 0.10, 0.40, 0.80),
)
```

Placement accepts:

- `bounds=(left, top, width, height)` in inches;
- `position="full"|"left"|"right"|"top"|"bottom"`;
- `relative_bounds=(x, y, width, height)` in the `0..1` range.

The selected bounds determine the diagram's available area. Layout computes
the aspect ratio internally and the renderer scales the resulting scene into
that area.

## Backends and Node.js

Geometry and visual style are separate options:

| Backend | Runtime | Behavior |
| --- | --- | --- |
| `native` (default) | Python only | Deterministic layout for all five typed diagram families |
| `official` | `mmdc` and Chromium | Mermaid computes SVG geometry, which is imported as editable shapes |
| `auto` | Automatic | Uses Official when `mmdc` is available, otherwise Native |

`pip install diagram-pptx` does not install Node.js. Here Node.js means the
JavaScript runtime, not a node in a diagram. It is required only when using
Official geometry.

```bash
npm install -g @mermaid-js/mermaid-cli@11.16.0
mmdc --version
diagram-pptx doctor
```

Selecting `backend="official"` without `mmdc` raises an actionable error with
installation instructions. `backend="auto"` falls back to Native and records
an informational diagnostic. Mermaid CLI 11.16.x is the supported Official
runtime; strict mode rejects a different version.

An unchanged partially modeled document can use Official to preserve its
original Mermaid source. Mutating a partial semantic model raises
`PartialModelMutationError` before source information can be lost.

## Themes and color maps

Apply an Official-like visual style while retaining Native geometry:

```python
render_mermaid(
    source,
    slide=slide,
    backend="native",
    style="official",
    colors={
        "name": "viridis",
        "primary": 0.82,
        "secondary": 0.18,
    },
)
```

Built-in continuous maps are `jet`, `viridis`, `plasma`, and `magma`.
`primary` controls ordinary fills. `secondary` is shorthand for decision
fills, outlines, connectors, and container lines. Channels such as `fill`,
`line`, `edge`, `text`, and `decision_fill` can be specified separately.

When no explicit text color is supplied, each filled node selects light or
dark text using relative luminance and contrast.

Default `source_style="merge"` precedence is:

```text
renderer defaults
< theme role defaults
< Mermaid classDef / inline style
< theme class and ID overrides
< render-time element override
< final color-map replacement
```

`preserve` gives explicit Mermaid styles priority. `replace` ignores Mermaid
visual properties while retaining semantic roles and classes. Versioned JSON
themes are supported without a YAML dependency.

## Mermaid support

| Family | Native semantic coverage in `0.1.0a1` |
| --- | --- |
| Flowchart | directions, common shapes, labeled/chained edges, cycles, self-loops, nested subgraphs, `classDef`, `class`, `style`, `linkStyle` |
| Sequence | participants, actors, messages, notes, activations, autonumber, `loop`, `alt`, `else`, `opt`, `par`, `critical`, `break` |
| Class | attributes, methods, stereotypes, namespaces, typed relationships, labels, notes, direction |
| ER | entity attributes, PK/FK/UK, cardinalities, relationship labels, direction |
| State | start/end, simple/composite states, transitions, notes, direction, choice/fork/join |

Unsupported statements are never silently dropped. They remain in
`MermaidDocument.raw_statements` with line/column diagnostics. `strict=True`
rejects unsupported syntax during parsing.

## CLI

```bash
diagram-pptx render input.mmd output.pptx \
  --backend native --style official --position left

diagram-pptx inspect input.mmd --json
diagram-pptx doctor
```

`inspect` reports the diagram family, modeled rate, diagnostics, preserved
statements, and required backend. `doctor` checks Python, `python-pptx`,
Mermaid CLI, image export, LibreOffice, and Poppler.

## Development environment

Docker is used for reproducible development and integration testing. It is
not needed by the normal Python API.

```bash
docker compose run --build --rm test
docker compose run --build --rm official-test
docker compose run --build --rm example
```

The fixed image contains Node.js, Mermaid CLI 11.16.0, Chromium, LibreOffice,
Poppler, and Noto CJK fonts. OOXML inspection and LibreOffice rendering are the
automated compatibility baseline; pixel-perfect identity with Microsoft
PowerPoint is not guaranteed.

For internals and new frontends/renderers, see
[architecture.md](architecture.md). For provider-neutral tool integration,
see [mcp-integration.md](mcp-integration.md).
