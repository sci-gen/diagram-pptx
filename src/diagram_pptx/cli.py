"""Command-line entry point for Mermaid-to-PPTX conversion."""

from __future__ import annotations

import argparse
from pathlib import Path

from pptx import Presentation
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

from .pipeline import render_mermaid


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="diagram-pptx",
        description="Render Mermaid flowcharts as editable native PowerPoint shapes.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    render = subparsers.add_parser("render", help="Render a Mermaid file to a new PPTX")
    render.add_argument("input", type=Path, help="Input .mmd file")
    render.add_argument("output", type=Path, help="Output .pptx file")
    render.add_argument("--title", help="Optional slide title")
    render.add_argument(
        "--bounds",
        default="0.7,1.0,11.93,5.9",
        help="left,top,width,height in inches (default: %(default)s)",
    )
    return parser


def _parse_bounds(value: str) -> tuple[float, float, float, float]:
    try:
        parts = tuple(float(part.strip()) for part in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("bounds must contain four numbers") from exc
    if len(parts) != 4 or parts[2] <= 0 or parts[3] <= 0:
        raise argparse.ArgumentTypeError("bounds must be left,top,positive-width,positive-height")
    return parts  # type: ignore[return-value]


def render_file(
    input_path: Path,
    output_path: Path,
    *,
    title: str | None = None,
    bounds: tuple[float, float, float, float] = (0.7, 1.0, 11.93, 5.9),
) -> None:
    source = input_path.read_text(encoding="utf-8")
    presentation = Presentation()
    presentation.slide_width = Inches(13.333)
    presentation.slide_height = Inches(7.5)
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])

    effective_bounds = bounds
    if title:
        title_box = slide.shapes.add_textbox(Inches(0.7), Inches(0.28), Inches(11.93), Inches(0.55))
        paragraph = title_box.text_frame.paragraphs[0]
        paragraph.alignment = PP_ALIGN.LEFT
        run = paragraph.add_run()
        run.text = title
        run.font.name = "Aptos Display"
        run.font.size = Pt(28)
        run.font.bold = True
        effective_bounds = (
            bounds[0],
            max(bounds[1], 1.05),
            bounds[2],
            min(bounds[3], 5.9),
        )

    render_mermaid(source, slide=slide, bounds=effective_bounds)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    presentation.save(output_path)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "render":
        try:
            bounds = _parse_bounds(args.bounds)
        except argparse.ArgumentTypeError as exc:
            parser.error(str(exc))
        render_file(args.input, args.output, title=args.title, bounds=bounds)
        return 0
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
