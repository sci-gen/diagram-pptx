import subprocess
from pathlib import Path

import pytest

from diagram_pptx import MermaidRuntimeError, official


def test_official_runtime_uses_argument_list_and_reads_svg(
    tmp_path: Path,
    monkeypatch,
) -> None:
    executable = tmp_path / "mmdc"
    executable.touch()
    calls: list[tuple[list[str], dict]] = []

    def fake_run(command, **options):
        calls.append((command, options))
        if "--version" in command:
            return subprocess.CompletedProcess(command, 0, "11.16.0\n", "")
        output = Path(command[command.index("-o") + 1])
        output.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
            '<rect x="1" y="1" width="8" height="8" fill="#ffffff"/>'
            "</svg>",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(official.subprocess, "run", fake_run)
    result = official.render_official_scene(
        "flowchart LR\nA",
        kind="flowchart",
        mmdc_path=str(executable),
        strict=True,
    )

    assert result.version == "11.16.0"
    assert result.scene.elements
    assert all(isinstance(command, list) for command, _ in calls)
    assert all("shell" not in options for _, options in calls)
    assert calls[-1][1]["timeout"] == 30.0


def test_strict_official_runtime_rejects_other_mermaid_series(
    tmp_path: Path,
    monkeypatch,
) -> None:
    executable = tmp_path / "mmdc"
    executable.touch()
    monkeypatch.setattr(official, "mmdc_version", lambda _: "12.0.0")

    with pytest.raises(MermaidRuntimeError, match="tested against 11.16.x"):
        official.render_official_scene(
            "flowchart LR\nA",
            kind="flowchart",
            mmdc_path=str(executable),
            strict=True,
        )


def test_official_runtime_reports_timeout(
    tmp_path: Path,
    monkeypatch,
) -> None:
    executable = tmp_path / "mmdc"
    executable.touch()
    monkeypatch.setattr(official, "mmdc_version", lambda _: "11.16.0")

    def time_out(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr(official.subprocess, "run", time_out)
    with pytest.raises(MermaidRuntimeError, match="exceeded the 0.1s timeout"):
        official.render_official_scene(
            "flowchart LR\nA",
            kind="flowchart",
            mmdc_path=str(executable),
            timeout=0.1,
        )
