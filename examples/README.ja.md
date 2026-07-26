<div align="right">
  <a href="README.md">English</a> · <strong>日本語</strong>
</div>

# Examples

以下は`diagram-pptx`が認識するMermaid 11.16の全syntax familyです。
Mermaid公式navigationの30図種に、同梱された実験的Railroadを加えた31図種です。

各画像は生成済みの
[31スライドPowerPoint](mermaid-syntax/mermaid-11.16-gallery.pptx)から描画しています。
PPTX内の図はすべて編集可能なPowerPoint図形で、図全体を1枚の画像として
貼り付けてはいません。

[![Mermaid 11.16全図種gallery](mermaid-syntax/overview.png)](build_mermaid_syntax_gallery.py)

- **Native**：型付きPythonモデル＋Pure Python layout。Node.js不要
- **Official → shapes**：Mermaid CLIでgeometryを計算し、編集可能なPowerPoint図形へ変換
- 全体画像をクリックするとPython生成スクリプトを表示
- 画像をクリックするとMermaid sourceを表示

| | |
| --- | --- |
| [![Flowchart](mermaid-syntax/images/flowchart.png)](mermaid-syntax/sources/flowchart.mmd)<br>**Flowchart** · Native | [![Swimlanes](mermaid-syntax/images/swimlanes.png)](mermaid-syntax/sources/swimlanes.mmd)<br>**Swimlanes** · Official → shapes |
| [![Sequence](mermaid-syntax/images/sequence.png)](mermaid-syntax/sources/sequence.mmd)<br>**Sequence** · Native | [![Class](mermaid-syntax/images/class.png)](mermaid-syntax/sources/class.mmd)<br>**Class** · Native |
| [![State](mermaid-syntax/images/state.png)](mermaid-syntax/sources/state.mmd)<br>**State** · Native | [![ER](mermaid-syntax/images/er.png)](mermaid-syntax/sources/er.mmd)<br>**ER** · Native |
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

## 再生成

全図種の生成にはMermaid CLI、Chromium、LibreOffice、Poppler、Noto fontが
必要なため、projectのDocker imageを使います。

```bash
docker run --rm \
  -v "$PWD:/workspace" \
  -w /workspace \
  diagram-pptx-dev \
  python examples/build_mermaid_syntax_gallery.py
```

生成される[manifest](mermaid-syntax/manifest.json)には、slide順、backend、source、
preview、編集可能shape数を記録します。
