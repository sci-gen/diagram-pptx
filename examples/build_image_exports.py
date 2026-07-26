"""Generate SVG, PNG, and JPEG from one mutable Mermaid document."""

from __future__ import annotations

import sys
from pathlib import Path

from diagram_pptx import parse_mermaid

SOURCE = """\
flowchart LR
    request[リクエスト] --> check{有効ですか？}
    check -->|はい| database[(データベース)]
    check -->|いいえ| reject[却下]
"""


def main(output_directory: str = "artifacts/image-export") -> None:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    diagram = parse_mermaid(SOURCE)
    colors = {"name": "viridis", "primary": 0.78, "secondary": 0.18}

    diagram.save(output / "diagram.svg", style="official", colors=colors)
    diagram.save(
        output / "diagram.png",
        dpi=300,
        background="transparent",
        style="official",
        colors=colors,
    )
    diagram.save(
        output / "diagram.jpg",
        dpi=300,
        background="#F7F8FA",
        quality=92,
        style="official",
        colors=colors,
    )


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "artifacts/image-export")
