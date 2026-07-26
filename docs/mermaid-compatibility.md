# Mermaid compatibility

[日本語](mermaid-compatibility.ja.md)

## Target and meaning of support

The compatibility target is Mermaid CLI **11.16.x**. Mermaid 11.16.0 exposes
30 diagram families in its public syntax navigation. Its distribution also
contains the experimental Railroad family, so `diagram-pptx` registers 31
families in total.

Support has three deliberately separate levels:

| Level | Meaning |
| --- | --- |
| Source-complete | `parse_mermaid()` recognizes the family and preserves the complete source without dropping statements |
| Official | Mermaid CLI parses and lays out the source; the SVG is converted to editable PowerPoint shapes |
| Typed + Native | A mutable family-specific Python model and Pure Python layout are available |

All 31 registered families are source-complete and covered by a pinned
Official integration fixture. Five have typed models and Native layouts.

Run `diagram-pptx support` or `diagram-pptx support --json` to obtain the same
matrix from the installed package.

## Family matrix

| Family | Declaration | Source | Official | Typed | Native |
| --- | --- | :---: | :---: | :---: | :---: |
| Flowchart | `flowchart`, `graph` | ✓ | ✓ | ✓ | ✓ |
| Swimlanes | `swimlane-beta` | ✓ | ✓ | — | — |
| Sequence | `sequenceDiagram` | ✓ | ✓ | ✓ | ✓ |
| Class | `classDiagram` | ✓ | ✓ | ✓ | ✓ |
| State | `stateDiagram`, `stateDiagram-v2` | ✓ | ✓ | ✓ | ✓ |
| Entity Relationship | `erDiagram` | ✓ | ✓ | ✓ | ✓ |
| User Journey | `journey` | ✓ | ✓ | — | — |
| Gantt | `gantt` | ✓ | ✓ | — | — |
| Pie / Donut | `pie` | ✓ | ✓ | — | — |
| Quadrant | `quadrantChart` | ✓ | ✓ | — | — |
| Requirement | `requirementDiagram` | ✓ | ✓ | — | — |
| GitGraph | `gitGraph` | ✓ | ✓ | — | — |
| C4 | `C4Context`, `C4Container`, and variants | ✓ | ✓ | — | — |
| Mindmap | `mindmap` | ✓ | ✓ | — | — |
| Timeline | `timeline` | ✓ | ✓ | — | — |
| ZenUML | `zenuml` | ✓ | ✓ | — | — |
| Sankey | `sankey`, `sankey-beta` | ✓ | ✓ | — | — |
| XY Chart | `xychart`, `xychart-beta` | ✓ | ✓ | — | — |
| Block | `block`, `block-beta` | ✓ | ✓ | — | — |
| Packet | `packet`, `packet-beta` | ✓ | ✓ | — | — |
| Kanban | `kanban` | ✓ | ✓ | — | — |
| Architecture | `architecture` | ✓ | ✓ | — | — |
| Radar | `radar-beta` | ✓ | ✓ | — | — |
| Event Modeling | `eventmodeling` | ✓ | ✓ | — | — |
| Treemap | `treemap` | ✓ | ✓ | — | — |
| Venn | `venn-beta` | ✓ | ✓ | — | — |
| Ishikawa | `ishikawa`, `ishikawa-beta` | ✓ | ✓ | — | — |
| Wardley | `wardley-beta` | ✓ | ✓ | — | — |
| Cynefin | `cynefin-beta` | ✓ | ✓ | — | — |
| TreeView | `treeView-beta` | ✓ | ✓ | — | — |
| Railroad (bundled experimental) | `railroad-*-beta` | ✓ | ✓ | — | — |

“Official ✓” means the pinned family fixture completes the full
`mmdc → SVG → DrawingScene → python-pptx` path and yields editable shapes. It
does not mean pixel-perfect browser identity. SVG gradients are approximated
with a solid stop color, curves become editable line segments, external
images are removed, and browser font metrics can differ.

## Current typed-model differences

The default `backend="native"` uses the typed subset below. A statement outside
that subset is preserved in the original document and works with
`backend="official"` as long as the partial typed model was not changed.

| Family | Typed and Native today | Official-only gaps |
| --- | --- | --- |
| Flowchart | directions; common shapes; labeled and chained edges; cycles and self-loops; nested subgraphs; `classDef`, `class`, `style`, `linkStyle` | v11.3 `@{ shape: ... }` catalog, icon/image nodes, markdown strings, edge IDs and animation, circle/cross/multidirectional arrows, `&` expansion, click/callback/link behavior, advanced curves |
| Sequence | participant/actor; common message arrows; notes; activation; basic autonumber; loop/alt/else/opt/par/critical/break/rect fragments | participant boxes, create/destroy, links and menus, autonumber start/increment formats, the full arrow matrix, advanced background/fragment details |
| Class | attributes, methods, stereotypes, namespaces, cardinalities, typed relations, labels, notes, direction | CSS class/style/click/link statements, generic and escaped member edge cases, lollipop interfaces, nested-namespace fidelity, advanced notes |
| ER | entities, attributes, PK/FK/UK, cardinalities, relationship labels, direction | entity aliases, optional attribute types and advanced identifiers, styling/classes, non-identifying dotted relations and newer attribute forms |
| State | start/end, simple/composite states, transitions, notes, direction, choice/fork/join | concurrent regions, class/style statements, extended descriptions, scale and advanced composite-state syntax |

This difference is intentional and visible:

- `document.is_fully_modeled` tells whether the typed model covers the source.
- `document.raw_statements` contains preserved statements from a typed family.
- `document.required_backend` is `official` when Native cannot safely compile.
- `document.modeling_rate` is `0.0` for a source-only family.
- `MermaidSourceDiagram.source` can be edited and recompiled with Official.

For source-only families, `strict=True` accepts the registered family;
Mermaid CLI performs the syntax validation when Official compilation runs.
For the five typed families, `strict=True` additionally requires every
statement to be representable in the typed model.

## Source-only example

```python
from diagram_pptx import parse_mermaid, compile_diagram

document = parse_mermaid("""
gantt
    title Release
    dateFormat YYYY-MM-DD
    Build :2026-08-01, 3d
""")

assert document.required_backend == "official"

compile_diagram(
    document,
    slide=slide,
    backend="official",
)
```

Node.js and Mermaid CLI are external runtimes:

```bash
npm install -g @mermaid-js/mermaid-cli@11.16.0
diagram-pptx doctor
```

