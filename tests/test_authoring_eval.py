import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "authoring_eval.py"
CASES = ROOT / "evals" / "cases" / "slide-authoring-v1.jsonl"


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_slide_authoring_cases_cover_controls_and_split_failures() -> None:
    cases = _read_jsonl(CASES)
    assert len(cases) >= 12
    assert len({case["id"] for case in cases}) == len(cases)
    assert {"avoid", "allow", "prefer"} <= {case["expected_split"] for case in cases}
    assert {"flowchart", "sequence", "class", "er", "state"} <= {
        case["diagram_kind"] for case in cases
    }
    assert any(case["mode"] == "preserve" for case in cases)
    assert any(case["language"] == "ja" for case in cases)


def test_prepare_builds_renderer_neutral_judge_item(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.jsonl"
    candidates.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "case_id": "flow-linear-release",
                "run_id": "skill-v1",
                "candidate_id": "release-1",
                "diagrams": [
                    {
                        "title": "Release flow",
                        "source": (
                            "flowchart LR\n"
                            "A[Intake] --> B[Review] --> C[Build] "
                            "--> D[Verify] --> E[Release]"
                        ),
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "prepared"
    command = [
        sys.executable,
        str(SCRIPT),
        "prepare",
        "--cases",
        str(CASES),
        "--candidates",
        str(candidates),
        "--output-dir",
        str(output_dir),
    ]
    has_png_support = importlib.util.find_spec("resvg_py") is not None
    if has_png_support:
        command.append("--png")
    process = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    item = _read_jsonl(output_dir / "judge-items.jsonl")[0]
    assert item["deterministic"]["hard_failures"] == []
    assert item["diagrams"][0]["primary_node_count"] == 5
    slide_svg = Path(item["diagrams"][0]["svg_path"])
    assert slide_svg.is_file()
    assert 'viewBox="0 0 1600 900"' in slide_svg.read_text(encoding="utf-8")
    assert Path(item["diagrams"][0]["diagram_svg_path"]).is_file()
    if has_png_support:
        png = Path(item["diagrams"][0]["png_path"])
        assert png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        from PIL import Image

        with Image.open(png) as preview:
            title_region = preview.convert("RGB").crop((60, 30, 500, 100))
            assert any(low < 255 for low, _high in title_region.getextrema())


def test_summarize_applies_regression_gate(tmp_path: Path) -> None:
    judgments = tmp_path / "judgments.jsonl"
    records = []
    for run_id, score in (("skill-v1", 4), ("skill-v2", 5)):
        records.append(
            {
                "schema_version": 1,
                "kind": "score",
                "case_id": "flow-linear-release",
                "run_id": run_id,
                "judge": {
                    "provider": "test",
                    "model": "judge",
                    "prompt_version": "v1",
                    "trial": 1,
                },
                "scores": {
                    "requirement_fidelity": score,
                    "slide_readability": score,
                    "visual_balance": score,
                    "information_granularity": score,
                    "structural_cohesion": score,
                    "split_quality": score,
                },
                "verdict": "pass",
                "hard_failures": [],
                "rationale": "test",
                "recommendations": [],
            }
        )
    judgments.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )
    output = tmp_path / "summary.json"
    process = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "summarize",
            "--judgments",
            str(judgments),
            "--baseline-run",
            "skill-v1",
            "--candidate-run",
            "skill-v2",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    summary = json.loads(output.read_text(encoding="utf-8"))
    assert summary["promotion"]["promote"] is True
    assert summary["promotion"]["dimension_deltas"]["slide_readability"] == 1


def test_summarize_resolves_blind_pairwise_order(tmp_path: Path) -> None:
    judgments = tmp_path / "judgments.jsonl"
    records = []
    for run_id in ("skill-v1", "skill-v2"):
        records.append(
            {
                "schema_version": 1,
                "kind": "score",
                "case_id": "flow-linear-release",
                "run_id": run_id,
                "judge": {
                    "provider": "test",
                    "model": "judge",
                    "prompt_version": "v1",
                    "trial": 1,
                },
                "scores": {
                    "requirement_fidelity": 5,
                    "slide_readability": 5,
                    "visual_balance": 5,
                    "information_granularity": 5,
                    "structural_cohesion": 5,
                    "split_quality": 5,
                },
                "verdict": "pass",
                "hard_failures": [],
                "rationale": "test",
                "recommendations": [],
            }
        )
    records.extend(
        [
            {
                "schema_version": 1,
                "kind": "pairwise",
                "case_id": "flow-linear-release",
                "run_a": "skill-v1",
                "run_b": "skill-v2",
                "presentation_order": ["skill-v1", "skill-v2"],
                "winner": "B",
                "judge": {
                    "provider": "test",
                    "model": "judge",
                    "prompt_version": "v1",
                    "trial": 1,
                },
                "rationale": "candidate wins",
            },
            {
                "schema_version": 1,
                "kind": "pairwise",
                "case_id": "flow-linear-release",
                "run_a": "skill-v1",
                "run_b": "skill-v2",
                "presentation_order": ["skill-v2", "skill-v1"],
                "winner": "A",
                "judge": {
                    "provider": "test",
                    "model": "judge",
                    "prompt_version": "v1",
                    "trial": 2,
                },
                "rationale": "candidate still wins after reversal",
            },
        ]
    )
    judgments.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )
    output = tmp_path / "summary.json"
    process = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "summarize",
            "--judgments",
            str(judgments),
            "--baseline-run",
            "skill-v1",
            "--candidate-run",
            "skill-v2",
            "--require-pairwise",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    summary = json.loads(output.read_text(encoding="utf-8"))
    comparison = summary["pairwise"]["skill-v1__vs__skill-v2"]
    assert comparison["wins"] == {"skill-v2": 2}
    assert summary["promotion"]["checks"]["pairwise_not_worse"] is True
