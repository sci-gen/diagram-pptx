from pathlib import Path

from pptx import Presentation

from diagram_pptx.cli import main


def test_cli_renders_a_presentation(tmp_path: Path) -> None:
    source = tmp_path / "diagram.mmd"
    output = tmp_path / "diagram.pptx"
    source.write_text("flowchart LR\nA[Start] --> B[Finish]", encoding="utf-8")

    status = main(["render", str(source), str(output), "--title", "Example"])

    assert status == 0
    assert output.exists()
    presentation = Presentation(output)
    assert len(presentation.slides) == 1
    assert len(presentation.slides[0].shapes) >= 4
