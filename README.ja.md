<div align="right">
  <a href="https://github.com/sci-gen/diagram-pptx/blob/main/README.md">English</a> · <strong>日本語</strong>
</div>

# diagram-pptx

**Mermaidから、編集可能なPowerPoint図形へ。**

[![CI](https://github.com/sci-gen/diagram-pptx/actions/workflows/ci.yml/badge.svg)](https://github.com/sci-gen/diagram-pptx/actions/workflows/ci.yml)
[![Python 3.10–3.13](https://img.shields.io/badge/python-3.10%E2%80%933.13-3776AB.svg)](https://www.python.org/)
[![MIT License](https://img.shields.io/badge/license-MIT-2EA44F.svg)](https://github.com/sci-gen/diagram-pptx/blob/main/LICENSE)
[![Package status](https://img.shields.io/badge/status-alpha-F59E0B.svg)](https://github.com/sci-gen/diagram-pptx/blob/main/CHANGELOG.md)

`diagram-pptx`はMermaidを型付きPythonモデルとして解析し、PowerPointの
AutoShape、コネクター、テキスト、グループとして描画します。同じ図を
SVG・PNG・JPEGへ保存することもできます。

<p align="center">
  <img
    src="https://raw.githubusercontent.com/sci-gen/diagram-pptx/main/docs/assets/readme/checkout-sequence.png"
    alt="diagram-pptxで生成した編集可能なチェックアウトのシーケンス図"
    width="100%"
  >
</p>

## インストール

```bash
pip install diagram-pptx
```

PNG・JPEG出力も利用する場合:

```bash
pip install "diagram-pptx[image]"
```

## 最速で使う

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

既定のNative描画にはNode.js、PowerPoint、Docker、LibreOfficeは不要です。
生成した図は移動・拡大縮小・グループ解除ができ、semantic IDから各要素を
参照できます。

```python
from diagram_pptx import parse_mermaid

diagram = parse_mermaid(source)
diagram.model.nodes["publish"].label = "Release"
diagram.save("diagram.svg")
diagram.save("diagram.png", dpi=300)
```

## 主な機能

- Flowchart、Sequence、Class、ER、Stateの5図種
- 型付き可変モデルによるparse・edit・compile
- `python-pptx`による編集可能なPowerPointネイティブ図形
- Pure PythonのNative layoutと、任意導入のMermaid CLI Official geometry
- テーマ、class/ID override、自動文字コントラスト、カラーマップ
- inch、スライド領域名、左上原点`0..1`による配置
- SVGと、高解像度PNG・JPEGへの任意出力

## ドキュメント

- [利用ガイド（英語）](https://github.com/sci-gen/diagram-pptx/blob/main/docs/user-guide.md)
- [Architecture・拡張契約（英語）](https://github.com/sci-gen/diagram-pptx/blob/main/docs/architecture.md)
- [MCP・Codex連携（英語）](https://github.com/sci-gen/diagram-pptx/blob/main/docs/mcp-integration.md)
- [Examples](https://github.com/sci-gen/diagram-pptx/tree/main/examples)
- [開発への参加](https://github.com/sci-gen/diagram-pptx/blob/main/CONTRIBUTING.md)
- [変更履歴](https://github.com/sci-gen/diagram-pptx/blob/main/CHANGELOG.md)

`0.1.0a1`はalpha版です。未対応のMermaid構文を黙って破棄せず、
診断として通知します。対応範囲とbackendの挙動は利用ガイドを参照してください。

## ライセンス

[MIT](https://github.com/sci-gen/diagram-pptx/blob/main/LICENSE)
