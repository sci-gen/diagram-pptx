# Mermaid互換性

[English](mermaid-compatibility.md)

## 対象versionと「対応」の意味

互換性の対象はMermaid CLI **11.16.x**です。Mermaid 11.16.0の公開syntax
navigationには30図種があります。配布物に含まれる実験的なRailroadも含め、
`diagram-pptx`は合計31ファミリーを登録しています。

「対応」は次の3段階に分けています。

| 段階 | 意味 |
| --- | --- |
| Source完全保持 | `parse_mermaid()`が図種を認識し、statementを欠落させずソース全体を保持 |
| Official | Mermaid CLIでparse/layoutし、SVGを編集可能なPowerPoint図形へ変換 |
| Typed + Native | 図種専用の可変PythonモデルとPure Python layoutを提供 |

31ファミリーすべてがSource完全保持と固定版Official integration fixtureの
対象です。このうち5図種がTyped + Nativeに対応します。

インストール済みpackageから同じ一覧を得るには
`diagram-pptx support`または`diagram-pptx support --json`を実行します。

## 図種一覧

| 図種 | 宣言 | Source | Official | Typed | Native |
| --- | --- | :---: | :---: | :---: | :---: |
| Flowchart | `flowchart`, `graph` | ✓ | ✓ | ✓ | ✓ |
| Swimlanes | `swimlane-beta` | ✓ | ✓ | — | — |
| Sequence | `sequenceDiagram` | ✓ | ✓ | ✓ | ✓ |
| Class | `classDiagram` | ✓ | ✓ | ✓ | ✓ |
| State | `stateDiagram`, `stateDiagram-v2` | ✓ | ✓ | ✓ | ✓ |
| ER | `erDiagram` | ✓ | ✓ | ✓ | ✓ |
| User Journey | `journey` | ✓ | ✓ | — | — |
| Gantt | `gantt` | ✓ | ✓ | — | — |
| Pie / Donut | `pie` | ✓ | ✓ | — | — |
| Quadrant | `quadrantChart` | ✓ | ✓ | — | — |
| Requirement | `requirementDiagram` | ✓ | ✓ | — | — |
| GitGraph | `gitGraph` | ✓ | ✓ | — | — |
| C4 | `C4Context`, `C4Container`など | ✓ | ✓ | — | — |
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
| Railroad（同梱・実験的） | `railroad-*-beta` | ✓ | ✓ | — | — |

「Official ✓」は、固定fixtureが
`mmdc → SVG → DrawingScene → python-pptx`を完走し、編集可能な図形を生成する
ことを意味します。browserとのpixel-perfect一致ではありません。SVG gradientは
単色stopへ近似し、curveは編集可能な線分へ変換し、外部画像は除去します。
browserとPowerPointではfont metricsも異なります。

## 現在のTypedモデルとの差分

既定の`backend="native"`は次のTyped subsetを使います。subset外のstatementも
元documentに保持され、partial modelを変更していなければ
`backend="official"`でそのまま描画できます。

| 図種 | 現在のTyped + Native | Officialのみの主な構文 |
| --- | --- | --- |
| Flowchart | direction、主要shape、label付き／連結edge、cycle、self-loop、nested subgraph、`classDef`、`class`、`style`、`linkStyle` | v11.3の`@{ shape: ... }`全shape、icon/image node、Markdown string、edge ID/animation、circle/cross/multidirectional arrow、`&`展開、click/callback/link、advanced curve |
| Sequence | participant/actor、主要message arrow、note、activation、基本autonumber、loop/alt/else/opt/par/critical/break/rect | participant box、create/destroy、link/menu、autonumberの開始値・増分format、全arrow matrix、高度な背景／fragment |
| Class | attribute、method、stereotype、namespace、cardinality、型付きrelation、label、note、direction | class/style/click/link、generic・escapeのedge case、lollipop interface、nested namespaceの完全保持、高度なnote |
| ER | entity、attribute、PK/FK/UK、cardinality、relationship label、direction | entity alias、optional attribute typeと高度なidentifier、style/class、非identifying dotted relation、新しいattribute form |
| State | start/end、simple/composite state、transition、note、direction、choice/fork/join | concurrent region、class/style、拡張description、scale、高度なcomposite syntax |

差分はAPIから確認できます。

- `document.is_fully_modeled`: Typedモデルがソース全体を表現できるか
- `document.raw_statements`: Typed図種で保持された未モデル化statement
- `document.required_backend`: Nativeで安全に処理できない場合は`official`
- `document.modeling_rate`: Source-only図種では`0.0`
- `MermaidSourceDiagram.source`: 編集後にOfficialで再compile可能な完全ソース

Source-only図種では`strict=True`でも登録済み図種を受理し、実際のsyntax検証は
Official compile時にMermaid CLIが行います。5つのTyped図種では
`strict=True`により、全statementがTypedモデルで表現できることも要求します。

## Source-only図種の例

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

Node.jsとMermaid CLIは外部runtimeです。

```bash
npm install -g @mermaid-js/mermaid-cli@11.16.0
diagram-pptx doctor
```

