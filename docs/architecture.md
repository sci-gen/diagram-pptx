# Architecture and OSS evolution

## Design objective

The core must not know Mermaid syntax or PowerPoint XML. It represents the
meaning of a graph and a positioned graph. Importers, layout engines, and
renderers are replaceable adapters around those two models.

```text
              ┌─────────────────┐
Mermaid ─────▶│                 │
JSON ────────▶│   Diagram IR    │
Graphviz ────▶│                 │
              └────────┬────────┘
                       │ LayoutEngine.apply()
                       ▼
              ┌─────────────────┐
              │  DiagramLayout  │
              │ nodes + routes  │
              └────────┬────────┘
                       │ DiagramRenderer.render()
             ┌─────────┼─────────┐
             ▼         ▼         ▼
          PowerPoint   SVG      future
```

The `contracts.py` protocols are structural. Third-party adapters do not need
to inherit framework base classes.

## Model boundaries

`Diagram` is semantic:

- node identity, label, shape intent, style tokens, and metadata
- directed or undirected edges and their labels
- groups and parent relationships
- reading/layout direction

`DiagramLayout` is geometric:

- positioned node boxes
- routed edge points
- positioned group boxes
- logical units independent of inches, EMUs, SVG pixels, or canvas size

Renderer-specific objects must not leak into either model. In particular,
`MSO_SHAPE`, Open XML elements, and python-pptx shape instances belong only in
`render/python_pptx.py`.

## Why diagram families should not share one graph IR

Flowcharts, dependency diagrams, and many state diagrams fit `Diagram`.
Sequence diagrams need lifelines and time ordering; ER diagrams need entities,
attributes, and cardinality; Gantt charts need time ranges and calendars.

A future package can add sibling semantic roots:

```text
Diagram
SequenceDiagram
EntityRelationshipDiagram
TimelineDiagram
```

They can still share styling primitives, renderer utilities, and public
packaging without corrupting the graph model with optional fields.

## PowerPoint rendering choices

1. AutoShape is preferred when `NodeShape` has a native PowerPoint equivalent.
2. Freeform should be the next adapter for shapes expressible as geometry.
3. SVG is a final fallback for shapes that cannot remain native.

Edges are created before nodes, keeping connectors behind entity shapes.
Grouped outlines are created first as backgrounds. Edge labels are separate
native text boxes because connector shapes cannot contain text.

The MVP uses routed straight segments rather than elbow connectors. Current
python-pptx connector attachment and elbow adjustment APIs are experimental;
explicit segments make generated geometry deterministic across LibreOffice and
PowerPoint.

## Proposed OSS phases

### Phase 1 — external package

Stabilize the following through real usage:

- Mermaid flowchart importer
- JSON interchange importer
- `Diagram` and `DiagramLayout`
- deterministic layered layout
- native python-pptx renderer
- rendered-image regression fixtures

### Phase 2 — focused python-pptx contributions

Contribute only low-level primitives proven necessary by the external package:

- public line arrowhead API
- public connector dash/line ending support
- reliable connection-site and elbow adjustment API
- group-shape authoring improvements
- native SVG insertion if upstream scope accepts it

Each contribution should be independently useful to python-pptx users and
should not mention Mermaid in its public API.

### Phase 3 — optional thin integration

After the IR and renderer are stable, consider a small helper such as
`ShapeTree.add_diagram(layout, ...)`. Keep parsing and layout outside
python-pptx.

## Compatibility policy

- Python: 3.10+
- python-pptx: 1.x
- IR additions are backward compatible within 0.x where practical.
- Breaking semantic changes require a changelog entry and a migration example.
- Importers should preserve unsupported source details under `metadata` when
  doing so is useful for round-tripping.

## Next implementation candidates

1. Golden-image regression tests with an explicit visual tolerance.
2. Edge port selection and collision avoidance.
3. Graphviz and ELK adapters behind optional dependencies.
4. Native PowerPoint grouping once group creation preserves desired z-order.
5. Separate semantic roots for sequence and ER diagrams.
