<div align="right">
  <strong>English</strong> · <a href="README.ja.md">日本語</a>
</div>

# Examples

The gallery below covers every Mermaid 11.16 syntax family recognized by
`diagram-pptx`: 30 families from Mermaid's public syntax navigation plus the
bundled experimental Railroad family.

Each preview is rendered from the generated
[31-slide PowerPoint deck](mermaid-syntax/mermaid-11.16-gallery.pptx).
Every diagram in that deck is made from editable PowerPoint shapes—there is no
full-diagram raster image embedded in the PPTX.

![Mermaid 11.16 diagram gallery](mermaid-syntax/overview.png)

- **Native**: typed Python model and Pure Python layout; no Node.js required.
- **Official → shapes**: Mermaid CLI supplies geometry, then `diagram-pptx`
  converts the SVG into editable PowerPoint shapes.
- Click a preview to open its Mermaid source.

| | |
| --- | --- |
| [![Flowchart](mermaid-syntax/images/flowchart.png)](mermaid-syntax/sources/flowchart.mmd)<br>**Flowchart** · Native | [![Swimlanes](mermaid-syntax/images/swimlanes.png)](mermaid-syntax/sources/swimlanes.mmd)<br>**Swimlanes** · Official → shapes |
| [![Sequence](mermaid-syntax/images/sequence.png)](mermaid-syntax/sources/sequence.mmd)<br>**Sequence** · Native | [![Class](mermaid-syntax/images/class.png)](mermaid-syntax/sources/class.mmd)<br>**Class** · Native |
| [![State](mermaid-syntax/images/state.png)](mermaid-syntax/sources/state.mmd)<br>**State** · Native | [![ER](mermaid-syntax/images/er.png)](mermaid-syntax/sources/er.mmd)<br>**Entity Relationship** · Native |
| [![Journey](mermaid-syntax/images/journey.png)](mermaid-syntax/sources/journey.mmd)<br>**User Journey** · Official → shapes | [![Gantt](mermaid-syntax/images/gantt.png)](mermaid-syntax/sources/gantt.mmd)<br>**Gantt** · Official → shapes |
| [![Pie](mermaid-syntax/images/pie.png)](mermaid-syntax/sources/pie.mmd)<br>**Pie / Donut** · Official → shapes | [![Quadrant](mermaid-syntax/images/quadrant.png)](mermaid-syntax/sources/quadrant.mmd)<br>**Quadrant** · Official → shapes |
| [![Requirement](mermaid-syntax/images/requirement.png)](mermaid-syntax/sources/requirement.mmd)<br>**Requirement** · Official → shapes | [![GitGraph](mermaid-syntax/images/gitgraph.png)](mermaid-syntax/sources/gitgraph.mmd)<br>**GitGraph** · Official → shapes |
| [![C4](mermaid-syntax/images/c4.png)](mermaid-syntax/sources/c4.mmd)<br>**C4** · Official → shapes | [![Mindmap](mermaid-syntax/images/mindmap.png)](mermaid-syntax/sources/mindmap.mmd)<br>**Mindmap** · Official → shapes |
| [![Timeline](mermaid-syntax/images/timeline.png)](mermaid-syntax/sources/timeline.mmd)<br>**Timeline** · Official → shapes | [![ZenUML](mermaid-syntax/images/zenuml.png)](mermaid-syntax/sources/zenuml.mmd)<br>**ZenUML** · Official → shapes |
| [![Sankey](mermaid-syntax/images/sankey.png)](mermaid-syntax/sources/sankey.mmd)<br>**Sankey** · Official → shapes | [![XY Chart](mermaid-syntax/images/xychart.png)](mermaid-syntax/sources/xychart.mmd)<br>**XY Chart** · Official → shapes |
| [![Block](mermaid-syntax/images/block.png)](mermaid-syntax/sources/block.mmd)<br>**Block** · Official → shapes | [![Packet](mermaid-syntax/images/packet.png)](mermaid-syntax/sources/packet.mmd)<br>**Packet** · Official → shapes |
| [![Kanban](mermaid-syntax/images/kanban.png)](mermaid-syntax/sources/kanban.mmd)<br>**Kanban** · Official → shapes | [![Architecture](mermaid-syntax/images/architecture.png)](mermaid-syntax/sources/architecture.mmd)<br>**Architecture** · Official → shapes |
| [![Radar](mermaid-syntax/images/radar.png)](mermaid-syntax/sources/radar.mmd)<br>**Radar** · Official → shapes | [![Event Modeling](mermaid-syntax/images/eventmodeling.png)](mermaid-syntax/sources/eventmodeling.mmd)<br>**Event Modeling** · Official → shapes |
| [![Treemap](mermaid-syntax/images/treemap.png)](mermaid-syntax/sources/treemap.mmd)<br>**Treemap** · Official → shapes | [![Venn](mermaid-syntax/images/venn.png)](mermaid-syntax/sources/venn.mmd)<br>**Venn** · Official → shapes |
| [![Ishikawa](mermaid-syntax/images/ishikawa.png)](mermaid-syntax/sources/ishikawa.mmd)<br>**Ishikawa** · Official → shapes | [![Wardley](mermaid-syntax/images/wardley.png)](mermaid-syntax/sources/wardley.mmd)<br>**Wardley** · Official → shapes |
| [![Cynefin](mermaid-syntax/images/cynefin.png)](mermaid-syntax/sources/cynefin.mmd)<br>**Cynefin** · Official → shapes | [![TreeView](mermaid-syntax/images/treeview.png)](mermaid-syntax/sources/treeview.mmd)<br>**TreeView** · Official → shapes |
| [![Railroad](mermaid-syntax/images/railroad.png)](mermaid-syntax/sources/railroad.mmd)<br>**Railroad** · Official → shapes | |

## Rebuild

Use the project Docker image because the complete gallery requires Mermaid CLI,
Chromium, LibreOffice, Poppler, and the Noto fonts:

```bash
docker run --rm \
  -v "$PWD:/workspace" \
  -w /workspace \
  diagram-pptx-dev \
  python examples/build_mermaid_syntax_gallery.py
```

The generated [manifest](mermaid-syntax/manifest.json) records slide order,
backend, source, preview, and editable shape count.
