"""Safe adapter around the external official Mermaid CLI."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .diagnostics import Diagnostic, MermaidRuntimeError
from .importers.mermaid_svg import import_mermaid_svg
from .scene import DrawingScene

SUPPORTED_MERMAID_SERIES = (11, 16)


@dataclass(slots=True)
class OfficialSceneResult:
    scene: DrawingScene
    version: str | None
    diagnostics: list[Diagnostic] = field(default_factory=list)


def find_mmdc(path: str | None = None) -> str | None:
    if path:
        candidate = Path(path)
        if candidate.is_file():
            return str(candidate.resolve())
        resolved = shutil.which(path)
        return resolved
    return shutil.which("mmdc")


def mmdc_version(path: str) -> str | None:
    try:
        result = subprocess.run(
            [path, "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    output = f"{result.stdout}\n{result.stderr}"
    match = re.search(r"\b(\d+\.\d+\.\d+(?:[-+][\w.-]+)?)\b", output)
    return match.group(1) if match else None


def render_official_scene(
    source: str,
    *,
    kind: str,
    mmdc_path: str | None = None,
    strict: bool = False,
    timeout: float = 30.0,
) -> OfficialSceneResult:
    executable = find_mmdc(mmdc_path)
    if executable is None:
        raise MermaidRuntimeError(
            "Official backend requires @mermaid-js/mermaid-cli. Install it with "
            "`npm install -g @mermaid-js/mermaid-cli@11.16.0`, pass mmdc_path, "
            "or use the project Docker image."
        )
    version = mmdc_version(executable)
    diagnostics: list[Diagnostic] = []
    if version:
        match = re.match(r"^(\d+)\.(\d+)", version)
        version_series = tuple(int(item) for item in match.groups()) if match else None
        if version_series != SUPPORTED_MERMAID_SERIES:
            diagnostic = Diagnostic(
                code="unsupported-mermaid-version",
                message=(
                    f"mmdc {version} is installed; SVG contracts are tested against "
                    f"{SUPPORTED_MERMAID_SERIES[0]}.{SUPPORTED_MERMAID_SERIES[1]}.x"
                ),
                backend="official",
            )
            if strict:
                raise MermaidRuntimeError(diagnostic.message)
            diagnostics.append(diagnostic)
    else:
        diagnostic = Diagnostic(
            code="unknown-mermaid-version",
            message="Could not determine the mmdc version",
            backend="official",
        )
        if strict:
            raise MermaidRuntimeError(diagnostic.message)
        diagnostics.append(diagnostic)

    with tempfile.TemporaryDirectory(prefix="diagram-pptx-mermaid-") as directory:
        root = Path(directory)
        input_path = root / "diagram.mmd"
        output_path = root / "diagram.svg"
        config_path = root / "config.json"
        puppeteer_path = root / "puppeteer.json"
        input_path.write_text(source, encoding="utf-8")
        config_path.write_text(
            json.dumps(
                {
                    "securityLevel": "strict",
                    "htmlLabels": True,
                    "deterministicIds": True,
                    "deterministicIDSeed": "diagram-pptx",
                }
            ),
            encoding="utf-8",
        )
        command = [
            executable,
            "-i",
            str(input_path),
            "-o",
            str(output_path),
            "-b",
            "transparent",
            "-c",
            str(config_path),
        ]
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            puppeteer_path.write_text(
                json.dumps({"args": ["--no-sandbox", "--disable-setuid-sandbox"]}),
                encoding="utf-8",
            )
            command.extend(["-p", str(puppeteer_path)])
        try:
            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise MermaidRuntimeError(f"mmdc exceeded the {timeout:g}s timeout") from exc
        except OSError as exc:
            raise MermaidRuntimeError(f"Could not execute mmdc: {exc}") from exc
        if process.returncode != 0:
            detail = (process.stderr or process.stdout).strip()
            raise MermaidRuntimeError(f"mmdc failed with exit code {process.returncode}: {detail}")
        if not output_path.is_file():
            raise MermaidRuntimeError("mmdc completed without producing an SVG file")
        svg = output_path.read_text(encoding="utf-8")
        lowered = svg.lower()
        if "<svg" not in lowered:
            raise MermaidRuntimeError("mmdc output is not SVG")
        visible_error_icon = re.search(
            r"""(?:class|id)\s*=\s*["'][^"']*\berror-icon\b""",
            svg,
            re.IGNORECASE,
        )
        if "syntax error in text" in lowered or visible_error_icon:
            raise MermaidRuntimeError("mmdc returned an SVG error document")
        scene = import_mermaid_svg(svg, kind=kind)
    return OfficialSceneResult(scene=scene, version=version, diagnostics=diagnostics)
