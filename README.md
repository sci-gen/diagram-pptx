# diagram-pptx

`diagram-pptx` turns declarative diagram sources into editable, native
PowerPoint shapes through `python-pptx`.

Mermaid is an importer, not the core model:

```text
Mermaid / JSON / future DSL
          │
          ▼
       Diagram IR
          │
          ▼
      LayoutEngine
          │
          ▼
     DiagramLayout
          │
          ▼
 python-pptx renderer
```

The package does not embed Mermaid SVG output. Nodes are PowerPoint AutoShapes,
and routes are PowerPoint connector shapes, so users can recolor, resize, and
edit them in PowerPoint-compatible applications.

## Status

This is a focused alpha/MVP. It supports common Mermaid `flowchart` syntax and
is intentionally not a complete Mermaid implementation. The stable design
surface is the IR and the importer/layout/renderer contracts.

## Quick start

```python
from pathlib import Path

from pptx import Presentation
from diagram_pptx import render_mermaid

source = """
flowchart LR
    A[Receive request] --> B{Valid?}
    B -->|Yes| C(Process)
    B -->|No| D[Reject]
"""

prs = Presentation()
slide = prs.slides.add_slide(prs.slide_layouts[6])
render_mermaid(source, slide=slide, bounds=(1.0, 1.0, 11.0, 5.5))
prs.save("diagram.pptx")
```

Or use the CLI:

```bash
diagram-pptx render flowchart.mmd flowchart.pptx --title "Request flow"
```

`bounds` uses inches and follows `(left, top, width, height)`.

## Mermaid flowchart subset

| Capability | Examples |
| --- | --- |
| Direction | `LR`, `RL`, `TB`/`TD`, `BT` |
| Nodes | `A[text]`, `A(text)`, `A{decision}`, `A((circle))` |
| More nodes | `A([stadium])`, `A[[subprocess]]`, `A{{hexagon}}` |
| Edges | `-->`, `---`, `==>`, `-.->`, chained edges |
| Edge labels | `A -->|yes| B` |
| Groups | `subgraph G[Label] ... end`, including nesting |
| Styles | `classDef`, `class`, and `style` with fill/stroke/color/width/dash |

Sequence, ER, Gantt, state, mindmap, and other Mermaid diagram families are
out of scope. They should receive separate semantic models instead of being
forced into a generic graph.

## Extension points

Import another syntax by producing `Diagram`:

```python
from diagram_pptx.model import Diagram, DiagramEdge, DiagramNode


class MyDslImporter:
    def parse(self, source: str) -> Diagram:
        diagram = Diagram(
            nodes=[DiagramNode("a", "Start"), DiagramNode("b", "Finish")],
            edges=[DiagramEdge("a", "b")],
        )
        diagram.validate()
        return diagram
```

Replace the layout engine without touching importers or renderers:

```python
diagram = MyDslImporter().parse(source)
layout = MyElkAdapter().apply(diagram)
PythonPptxRenderer().render(layout, target=slide, bounds=(1, 1, 11, 5.5))
```

The JSON importer is the reference interchange adapter:

```python
from diagram_pptx.importers import JsonImporter

diagram = JsonImporter().parse(
    {
        "direction": "TB",
        "nodes": [
            {"id": "a", "label": "Start"},
            {"id": "b", "label": "Approve?", "shape": "diamond"},
        ],
        "edges": [{"source": "a", "target": "b"}],
    }
)
```

## Docker development

No local PowerPoint installation is required.

```bash
docker compose run --build --rm test
docker compose run --build --rm example
```

The example command creates:

- `artifacts/flowchart.pptx`
- `artifacts/rendered/flowchart.pdf`
- `artifacts/rendered/slide-1.png`

LibreOffice Impress performs the headless PPTX-to-PDF conversion, and Poppler
rasterizes the PDF. The test suite also opens the generated package and asserts
that the slide contains connector and AutoShape XML but no raster image.

## Current renderer trade-offs

- Orthogonal routes use multiple straight native connectors. This preserves
  editability and avoids python-pptx's currently experimental elbow connector
  routing, but moving one node does not automatically reroute the full path.
- Arrowheads and dash presets are written as standard DrawingML line
  properties because python-pptx 1.0.2 does not expose all of them publicly.
- Unknown/custom node shapes fall back to a rectangle. A future freeform or SVG
  renderer can be registered without changing the IR.
- The bundled layered layout is deterministic and dependency-light. Complex
  crossing minimization or ports should be implemented by a Graphviz/ELK
  adapter.

See [the architecture notes](docs/architecture.md) for package boundaries and
the proposed OSS evolution path.

## License

MIT
