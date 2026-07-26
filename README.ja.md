<div align="right">
  <a href="./README.md">English</a> · <strong>日本語</strong>
</div>

# diagram-pptx

**Mermaidを入力し、編集可能なPowerPoint図形として出力します。**

[![Python 3.10–3.13](https://img.shields.io/badge/python-3.10%E2%80%933.13-3776AB.svg)](https://www.python.org/)
[![MIT License](https://img.shields.io/badge/license-MIT-2EA44F.svg)](LICENSE)
[![Package status](https://img.shields.io/badge/status-alpha-F59E0B.svg)](#プロジェクトの状態)
[![Editable PPTX](https://img.shields.io/badge/output-editable%20PPTX-CC2927.svg)](#native-pptxが重要な理由)

`diagram-pptx`は、Pythonネイティブの図形オブジェクトモデル兼コンパイラです。
Mermaidを解析して型付きモデルへ変換し、Pythonから参照・変更したうえで、
PowerPointのAutoShape、コネクター、テキスト、グループとして描画します。
同じオブジェクトをSVG、PNG、JPEGとして保存することもできます。

<p align="center">
  <img
    src="./docs/assets/readme/checkout-sequence.png"
    alt="diagram-pptxで生成した架空のチェックアウトシーケンス図"
    width="100%"
  >
</p>

上の図は公開用に作成した架空データです。Mermaidから生成され、Pythonでは
各要素をsemantic IDで参照できます。

## 最速で使う

```bash
pip install diagram-pptx
```

```python
from pptx import Presentation
from diagram_pptx import render_mermaid

source = """
flowchart LR
    request[Request] --> review{Approved?}
    review -->|yes| publish[Publish]
    review -->|no| request
"""

prs = Presentation()
slide = prs.slides.add_slide(prs.slide_layouts[6])

render_mermaid(source, slide=slide, position="full")
prs.save("diagram.pptx")
```

これだけで、PowerPoint上で移動・拡大縮小・グループ解除できる図を作成できます。
Native描画には、PowerPoint、Node.js、Chromium、Docker、LibreOfficeは不要です。

## 主な特徴

| 機能 | 内容 |
| --- | --- |
| 編集可能なPowerPoint | スクリーンショットではなく、ネイティブ図形とコネクターを生成 |
| 型付きPythonモデル | Flow、Sequence、Class、ER、Stateを別々のモデルとして提供 |
| ORMのような編集 | `model.nodes["db"]`やsemanticな`select()`で直接操作 |
| Mermaid frontend | 行・列情報、診断、strict解析、canonical serializer |
| 2つのgeometry backend | Pure PythonのNativeとMermaid CLIを使うOfficial |
| 再利用可能なスタイル | テーマ、role、class/ID override、RGBA、連続カラーマップ |
| 柔軟な配置 | inch指定、左右上下プリセット、`0..1`の相対座標 |
| 画像出力 | 追加依存なしのSVGと、高解像度PNG/JPEG |
| Agent向けAPI | 型付き引数とMCP等で使えるJSON-safeな結果 |

```text
Mermaid / JSON / 将来のfrontend
                ↓
        typed semantic model
                ↓
              layout
                ↓
          DrawingScene
                ↓
         style resolution
         ↙      ↓      ↘
 編集可能    SVG    PNG/JPEG
   PPTX
```

Mermaidは主要な宣言的frontendであり、内部表現そのものではありません。
各rendererはMermaid構文ではなく`DrawingScene`を入力にします。

## 解析・編集・コンパイル

```python
from pptx import Presentation
from diagram_pptx import compile_diagram, parse_mermaid

source = """
flowchart LR
    api([API]) --> db[(Database)]
"""

diagram = parse_mermaid(source)
diagram.model.nodes["db"].label = "Primary DB"
diagram.model.nodes["db"].classes.add("storage")

prs = Presentation()
slide = prs.slides.add_slide(prs.slide_layouts[6])

result = compile_diagram(
    diagram,
    slide=slide,
    bounds=(1, 1, 11, 5.5),
    style="official",
    group=True,
)

# グループ化後もpython-pptxオブジェクトへアクセスできます。
result.element_shapes["db"].text = "Primary database"
result.group_shape.width = int(result.group_shape.width * 1.1)
prs.save("database-flow.pptx")
```

IDを持つsemantic要素は可変dataclassで、挿入順を保つ辞書へ格納されます。
アプリケーションやtool callから扱いやすい、小さく予測可能なAPIです。

## SVG・PNG・JPEGへ保存

PNG・JPEGを使う場合はimage extraを追加します。

```bash
pip install "diagram-pptx[image]"
```

任意runtime機能をまとめて導入する場合は`all`を使います。

```bash
pip install "diagram-pptx[all]"
```

同じ解析済みオブジェクトを、Matplotlibに近い感覚で保存できます。

```python
diagram.save("diagram.svg")
diagram.save("diagram.png", dpi=600, background="transparent")
diagram.save("diagram.jpg", dpi=300, background="#FFFFFF", quality=92)

svg_text = diagram.to_svg()
png_bytes = diagram.to_png(dpi=300)
jpeg_bytes = diagram.to_jpeg(dpi=300)
```

- SVGはベクター形式で、追加パッケージは不要です。
- PNGは透過背景に対応します。
- JPEGは透過部分を指定背景色へ合成します。
- `width_px`と`height_px`でピクセル寸法を指定できます。
- 最大ピクセル数の制限により、巨大画像の誤生成を防ぎます。

## Flowchart

<p align="center">
  <img
    src="./docs/assets/readme/order-fulfillment-flow.png"
    alt="diagram-pptxで生成した架空の注文処理フローチャート"
    width="100%"
  >
</p>

この公開用サンプルでは、decision、cycle、label付きbranch、terminal shape、
ID別styleを確認できます。特定のプロジェクトや業務の情報は含みません。

## BackendとNode.js

| Backend | Runtime | 動作 |
| --- | --- | --- |
| `native`（既定） | Pythonのみ | 5つの型付き図種を決定論的に配置 |
| `official` | `mmdc` + Chromium | Mermaidがgeometryを計算し、SVG geometryを編集可能な図形へ変換 |
| `auto` | 自動 | `mmdc`があればOfficial、なければNative |

`pip install diagram-pptx`ではNode.jsはインストールされません。ここでいう
Node.jsは図のnodeではなくJavaScript runtimeで、Official geometryを使う場合だけ
必要です。

```bash
npm install -g @mermaid-js/mermaid-cli@11.16.0
mmdc --version
diagram-pptx doctor
```

`mmdc`なしで`backend="official"`を選ぶと、導入手順を含むエラーになります。
`backend="auto"`ではNativeへ切り替え、情報diagnosticを返します。
開発用Docker imageには固定版のOfficial runtimeが含まれます。

## テーマとカラーマップ

geometry backendと見た目のstyleは独立しています。

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

組み込みの連続カラーマップは`jet`、`viridis`、`plasma`、`magma`です。
`primary`は通常nodeのfill、`secondary`はdecision fill、outline、
connector、container lineの短縮指定です。`fill`、`line`、`edge`、`text`、
`decision_fill`を個別に指定することもできます。

文字色を指定しない場合、各nodeが相対輝度とcontrastに基づいて白または濃色を
自動選択します。

既定の`source_style="merge"`では、次の順でstyleを解決します。

```text
renderer defaults
< theme role defaults
< Mermaid classDef / inline style
< theme class and ID overrides
< render-time element override
< final color-map replacement
```

versioned JSON themeに対応しています。YAML依存は追加していません。

## 既存スライドへの配置

```python
render_mermaid(left_source, slide=slide, position="left")
render_mermaid(right_source, slide=slide, position="right")
```

相対座標でも配置できます。

```python
render_mermaid(
    source,
    slide=slide,
    relative_bounds=(0.05, 0.10, 0.40, 0.80),
)
```

指定方法は次の3種類です。

- `bounds=(left, top, width, height)`：inch指定
- `position="full"|"left"|"right"|"top"|"bottom"`：領域プリセット
- `relative_bounds=(x, y, width, height)`：左上原点の`0..1`相対座標

## Mermaid対応範囲

| 図種 | `0.1.0a1`のNative対応 |
| --- | --- |
| Flowchart | direction、主要shape、label付きedge、chain、cycle、self-loop、nested subgraph、`classDef`、`class`、`style`、`linkStyle` |
| Sequence | participant、actor、message、note、activation、autonumber、`loop`、`alt`、`else`、`opt`、`par`、`critical`、`break` |
| Class | attribute、method、stereotype、namespace、各relation、label、note、direction |
| ER | entity attribute、PK/FK/UK、cardinality、relationship label、direction |
| State | start/end、simple/composite state、transition、note、direction、choice/fork/join |

未対応statementを黙って欠落させることはありません。
`MermaidDocument.raw_statements`へ元のstatementを保持し、行・列付きdiagnosticを
返します。変更されていないpartial documentはOfficialで描画できます。
partial semantic modelを変更すると、情報欠落を防ぐため
`PartialModelMutationError`になります。`strict=True`ではparse時に拒否します。

## CLI

```bash
diagram-pptx render input.mmd output.pptx \
  --backend native --style official --position left

diagram-pptx inspect input.mmd --json
diagram-pptx doctor
```

`inspect`は図種、モデル化率、diagnostic、保持statement、必要backendを表示します。
`doctor`はPython、`python-pptx`、Mermaid CLI、SVG/PNG/JPEG、
LibreOffice、Popplerを確認します。

## Tool・Agent連携

core packageはprovider-neutralです。ベンダー専用のfunction schemaは含めません。
MCP server、Codex plugin、その他のadapterは同じ型付きPython APIを呼び出し、
`CompileResult.to_dict()`または`ExportResult.to_dict()`を返せます。

FastMCP adapter、plugin manifest、skill例は
[MCP and Codex integration](docs/mcp-integration.md)を参照してください。

## Docker開発

```bash
docker compose run --build --rm test
docker compose run --build --rm official-test
docker compose run --build --rm example
```

固定Docker環境には、Node.js、Mermaid CLI 11.16.0、Chromium、
LibreOffice、Poppler、Noto CJK fontが含まれます。Dockerは開発・integration
test環境であり、通常のPython API利用には不要です。

## Native PPTXが重要な理由

SVGやPNGはpreviewや公開には便利ですが、編集可能なPowerPoint objectの代わりには
なりません。Native出力では、コンパイル後も個々のsemantic要素を移動、拡大縮小、
グループ解除、style変更、Pythonからの再参照が可能です。本パッケージは汎用的な
SVG入力→PowerPoint変換器ではありません。

## プロジェクトの状態

`0.1.0a1`はalpha APIです。Native testはPython 3.10–3.13で実行します。
Official integrationとPPTX→PDF→PNGのvisual checkは固定Docker環境で実行します。
自動互換性確認はOOXMLとLibreOfficeを基準とし、Microsoft PowerPointとの
pixel-perfectな同一性は保証しません。

## ライセンス

[MIT](LICENSE)

拡張contractは[architecture.md](docs/architecture.md)、開発手順は
[CONTRIBUTING.md](CONTRIBUTING.md)を参照してください。
