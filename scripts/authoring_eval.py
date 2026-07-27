"""Prepare and summarize provider-neutral Mermaid slide-authoring evaluations."""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from statistics import fmean
from typing import Any

from diagram_pptx import build_scene, parse_mermaid, to_svg
from diagram_pptx.scene import SceneConnector, SceneContainer, SceneShape, SceneText

SCORE_DIMENSIONS = (
    "requirement_fidelity",
    "slide_readability",
    "visual_balance",
    "information_granularity",
    "structural_cohesion",
    "split_quality",
)
SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")
SVG_NAMESPACE = "http://www.w3.org/2000/svg"
SLIDE_WIDTH_PX = 1600
SLIDE_HEIGHT_PX = 900

ET.register_namespace("", SVG_NAMESPACE)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, raw_line in enumerate(stream, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: each JSONL record must be an object")
            records.append(value)
    return records


def _write_jsonl(path: Path, records: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            stream.write("\n")


def _require_safe_id(value: Any, *, field: str) -> str:
    text = str(value or "")
    if not SAFE_ID.fullmatch(text):
        raise ValueError(f"{field} must match {SAFE_ID.pattern!r}, got {text!r}")
    return text


def _semantic_count(model: Any, names: tuple[str, ...]) -> int:
    for name in names:
        value = getattr(model, name, None)
        if isinstance(value, (dict, list, tuple)):
            return len(value)
    return 0


def _target_aspect(case: Mapping[str, Any]) -> tuple[float, float]:
    explicit = case.get("target_aspect_ratio")
    if isinstance(explicit, Mapping):
        return float(explicit["min"]), float(explicit["max"])
    return (0.55, 1.15) if case.get("slide_region") == "half" else (1.3, 2.2)


def _normalized_source(value: str) -> str:
    return value.replace("\r\n", "\n").strip()


def _place_on_slide(svg: str, *, title: str, slide_region: str) -> str:
    inner = ET.fromstring(svg)
    x, y, width, height = (80, 120, 700, 700) if slide_region == "half" else (80, 120, 1440, 700)
    inner.set("x", str(x))
    inner.set("y", str(y))
    inner.set("width", str(width))
    inner.set("height", str(height))
    inner.set("preserveAspectRatio", "xMidYMid meet")

    root = ET.Element(
        f"{{{SVG_NAMESPACE}}}svg",
        {
            "width": str(SLIDE_WIDTH_PX),
            "height": str(SLIDE_HEIGHT_PX),
            "viewBox": f"0 0 {SLIDE_WIDTH_PX} {SLIDE_HEIGHT_PX}",
        },
    )
    ET.SubElement(
        root,
        f"{{{SVG_NAMESPACE}}}rect",
        {
            "x": "0",
            "y": "0",
            "width": str(SLIDE_WIDTH_PX),
            "height": str(SLIDE_HEIGHT_PX),
            "fill": "#FFFFFF",
        },
    )
    title_element = ET.SubElement(
        root,
        f"{{{SVG_NAMESPACE}}}text",
        {
            "x": "80",
            "y": "72",
            "fill": "#172033",
            "font-family": "Arial, Noto Sans, sans-serif",
            "font-size": "32",
            "font-weight": "600",
        },
    )
    title_element.text = title
    root.append(inner)
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def _slide_png(svg: str) -> bytes:
    try:
        import resvg_py
    except ImportError as exc:
        raise RuntimeError(
            'PNG evaluation previews require `pip install "diagram-pptx[image]"`.'
        ) from exc
    return bytes(
        resvg_py.svg_to_bytes(
            svg_string=svg,
            width=SLIDE_WIDTH_PX,
            height=SLIDE_HEIGHT_PX,
            dpi=96,
            sans_serif_family="DejaVu Sans",
        )
    )


def _prepare_candidate(
    candidate: Mapping[str, Any],
    case: Mapping[str, Any],
    *,
    output_dir: Path,
    backend: str,
    render_png: bool,
    strict: bool,
) -> dict[str, Any]:
    run_id = _require_safe_id(candidate.get("run_id"), field="run_id")
    candidate_id = _require_safe_id(candidate.get("candidate_id"), field="candidate_id")
    diagrams = candidate.get("diagrams")
    if not isinstance(diagrams, list) or not diagrams:
        raise ValueError(f"{candidate_id}: diagrams must be a non-empty array")

    case_id = str(case["id"])
    artifact_dir = output_dir / "artifacts" / run_id / case_id / candidate_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    hard_failures: list[str] = []
    warnings: list[str] = []
    expected_count = case["expected_diagram_count"]
    if not int(expected_count["min"]) <= len(diagrams) <= int(expected_count["max"]):
        hard_failures.append("diagram_count_out_of_range")
    if case.get("mode") == "preserve":
        preserved = len(diagrams) == 1 and _normalized_source(
            str(diagrams[0].get("source", ""))
        ) == _normalized_source(str(case.get("source", "")))
        if not preserved:
            hard_failures.append("unauthorized_source_change")

    target_min, target_max = _target_aspect(case)
    diagram_results: list[dict[str, Any]] = []
    for index, diagram in enumerate(diagrams, start=1):
        if not isinstance(diagram, Mapping):
            raise ValueError(f"{candidate_id}: diagram {index} must be an object")
        source = str(diagram.get("source", ""))
        title = str(diagram.get("title", f"Diagram {index}"))
        if not source.strip():
            hard_failures.append(f"diagram_{index}:empty_source")
            continue
        try:
            document = parse_mermaid(source, strict=strict)
            result = build_scene(
                document,
                backend=backend,
                style="official",
                strict=strict,
            )
            scene = result.scene
            aspect_ratio = scene.width / max(scene.height, 1e-9)
            primary_nodes = _semantic_count(
                document.model,
                ("nodes", "participants", "classes", "entities", "states"),
            )
            relations = _semantic_count(
                document.model,
                ("edges", "events", "relationships", "transitions"),
            )
            if not target_min <= aspect_ratio <= target_max:
                warnings.append(f"diagram_{index}:aspect_ratio_outside_target")
            if primary_nodes > int(case["max_primary_nodes_per_diagram"]):
                warnings.append(f"diagram_{index}:primary_node_budget_exceeded")

            stem = f"{index:02d}"
            diagram_svg = to_svg(
                document,
                backend=backend,
                style="official",
                background=None,
                label_background="#FFFFFF",
            )
            diagram_svg_path = artifact_dir / f"{stem}-diagram.svg"
            diagram_svg_path.write_text(diagram_svg, encoding="utf-8")
            slide_svg = _place_on_slide(
                diagram_svg,
                title=title,
                slide_region=str(case["slide_region"]),
            )
            svg_path = artifact_dir / f"{stem}.svg"
            svg_path.write_text(slide_svg, encoding="utf-8")
            png_path: Path | None = None
            if render_png:
                png_path = artifact_dir / f"{stem}.png"
                png_path.write_bytes(_slide_png(slide_svg))
            diagram_results.append(
                {
                    "index": index,
                    "title": title,
                    "source": source,
                    "kind": scene.kind,
                    "backend_used": result.backend_used,
                    "is_fully_modeled": document.is_fully_modeled,
                    "modeling_rate": document.modeling_rate,
                    "primary_node_count": primary_nodes,
                    "relation_or_event_count": relations,
                    "scene_width": scene.width,
                    "scene_height": scene.height,
                    "scene_aspect_ratio": aspect_ratio,
                    "aspect_target": {"min": target_min, "max": target_max},
                    "scene_elements": {
                        "shapes": sum(isinstance(item, SceneShape) for item in scene.elements),
                        "connectors": sum(
                            isinstance(item, SceneConnector) for item in scene.elements
                        ),
                        "containers": sum(
                            isinstance(item, SceneContainer) for item in scene.elements
                        ),
                        "texts": sum(isinstance(item, SceneText) for item in scene.elements),
                    },
                    "diagnostics": [item.to_dict() for item in result.diagnostics],
                    "svg_path": str(svg_path.resolve()),
                    "diagram_svg_path": str(diagram_svg_path.resolve()),
                    "png_path": str(png_path.resolve()) if png_path else None,
                }
            )
        except Exception as exc:  # preserve failures as judge-visible evidence
            hard_failures.append(f"diagram_{index}:render_error:{type(exc).__name__}")
            diagram_results.append(
                {
                    "index": index,
                    "title": title,
                    "source": source,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    return {
        "schema_version": 1,
        "case": dict(case),
        "candidate": {
            "schema_version": candidate.get("schema_version", 1),
            "case_id": case_id,
            "run_id": run_id,
            "candidate_id": candidate_id,
            "generator": candidate.get("generator", {}),
            "notes": candidate.get("notes", ""),
        },
        "deterministic": {
            "diagram_count": len(diagrams),
            "hard_failures": sorted(set(hard_failures)),
            "warnings": sorted(set(warnings)),
        },
        "diagrams": diagram_results,
    }


def prepare(args: argparse.Namespace) -> int:
    cases = _read_jsonl(args.cases)
    cases_by_id = {str(case["id"]): case for case in cases}
    if len(cases_by_id) != len(cases):
        raise ValueError("Case IDs must be unique")
    prepared: list[dict[str, Any]] = []
    for candidate in _read_jsonl(args.candidates):
        case_id = str(candidate.get("case_id", ""))
        try:
            case = cases_by_id[case_id]
        except KeyError as exc:
            raise ValueError(f"Unknown case_id: {case_id!r}") from exc
        prepared.append(
            _prepare_candidate(
                candidate,
                case,
                output_dir=args.output_dir,
                backend=args.backend,
                render_png=args.png,
                strict=args.strict,
            )
        )
    output = args.output_dir / "judge-items.jsonl"
    _write_jsonl(output, prepared)
    hard_failure_count = sum(len(item["deterministic"]["hard_failures"]) for item in prepared)
    print(
        json.dumps(
            {
                "candidate_count": len(prepared),
                "hard_failure_count": hard_failure_count,
                "judge_items": str(output.resolve()),
            },
            indent=2,
        )
    )
    return 1 if hard_failure_count else 0


def _score_summary(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    dimension_values: dict[str, list[float]] = defaultdict(list)
    verdicts = Counter()
    failures = Counter()
    overall_values: list[float] = []
    for record in records:
        scores = record.get("scores")
        if not isinstance(scores, Mapping):
            raise ValueError("score records require a scores object")
        values = []
        for dimension in SCORE_DIMENSIONS:
            score = float(scores[dimension])
            if not 1 <= score <= 5:
                raise ValueError(f"{dimension} must be between 1 and 5")
            dimension_values[dimension].append(score)
            values.append(score)
        overall_values.append(fmean(values))
        verdicts[str(record.get("verdict"))] += 1
        failures.update(str(item) for item in record.get("hard_failures", []))
    count = len(records)
    return {
        "judgment_count": count,
        "case_count": len({str(item["case_id"]) for item in records}),
        "pass_rate": verdicts["pass"] / count if count else 0.0,
        "overall_mean": fmean(overall_values) if overall_values else 0.0,
        "dimension_means": {
            name: fmean(values) for name, values in sorted(dimension_values.items())
        },
        "hard_failure_count": sum(failures.values()),
        "hard_failures": dict(failures.most_common()),
    }


def _pairwise_summary(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    grouped: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for record in records:
        run_a = str(record["run_a"])
        run_b = str(record["run_b"])
        presentation_order = [str(item) for item in record["presentation_order"]]
        if len(presentation_order) != 2 or set(presentation_order) != {run_a, run_b}:
            raise ValueError("presentation_order must contain run_a and run_b exactly once")
        blind_winner = str(record["winner"])
        if blind_winner == "tie":
            winner = "tie"
        elif blind_winner == "A":
            winner = presentation_order[0]
        elif blind_winner == "B":
            winner = presentation_order[1]
        else:
            raise ValueError("pairwise winner must be A, B, or tie")
        pair = tuple(sorted((run_a, run_b)))
        grouped[pair][winner] += 1
    return {
        f"{pair[0]}__vs__{pair[1]}": {
            "comparison_count": sum(winners.values()),
            "wins": dict(winners),
        }
        for pair, winners in sorted(grouped.items())
    }


def summarize(args: argparse.Namespace) -> int:
    records = _read_jsonl(args.judgments)
    score_records: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    pairwise_records: list[Mapping[str, Any]] = []
    for record in records:
        kind = record.get("kind")
        if kind == "score":
            score_records[str(record["run_id"])].append(record)
        elif kind == "pairwise":
            pairwise_records.append(record)
        else:
            raise ValueError(f"Unknown judgment kind: {kind!r}")
    runs = {run_id: _score_summary(items) for run_id, items in sorted(score_records.items())}
    pairwise = _pairwise_summary(pairwise_records)
    output: dict[str, Any] = {
        "schema_version": 1,
        "runs": runs,
        "pairwise": pairwise,
    }

    promote = True
    if args.candidate_run:
        if args.candidate_run not in runs:
            raise ValueError(f"Unknown candidate run: {args.candidate_run!r}")
        candidate = runs[args.candidate_run]
        checks = {
            "pass_rate": candidate["pass_rate"] >= args.min_pass_rate,
            "overall_mean": candidate["overall_mean"] >= args.min_overall,
            "no_hard_failures": candidate["hard_failure_count"] == 0,
        }
        deltas: dict[str, float] = {}
        if args.baseline_run:
            if args.baseline_run not in runs:
                raise ValueError(f"Unknown baseline run: {args.baseline_run!r}")
            baseline = runs[args.baseline_run]
            deltas = {
                name: candidate["dimension_means"][name] - baseline["dimension_means"][name]
                for name in SCORE_DIMENSIONS
            }
            checks["no_dimension_regression"] = all(
                value >= -args.max_dimension_regression for value in deltas.values()
            )
            pair_key = "__vs__".join(sorted((args.baseline_run, args.candidate_run)))
            comparison = pairwise.get(pair_key)
            if comparison:
                wins = comparison["wins"]
                checks["pairwise_not_worse"] = wins.get(args.candidate_run, 0) >= wins.get(
                    args.baseline_run, 0
                )
            elif args.require_pairwise:
                checks["pairwise_present"] = False
        promote = all(checks.values())
        output["promotion"] = {
            "baseline_run": args.baseline_run,
            "candidate_run": args.candidate_run,
            "checks": checks,
            "dimension_deltas": deltas,
            "promote": promote,
        }

    serialized = json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0 if promote else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser(
        "prepare",
        help="render candidates and build judge items",
    )
    prepare_parser.add_argument(
        "--cases",
        type=Path,
        default=Path("evals/cases/slide-authoring-v1.jsonl"),
    )
    prepare_parser.add_argument("--candidates", type=Path, required=True)
    prepare_parser.add_argument("--output-dir", type=Path, required=True)
    prepare_parser.add_argument(
        "--backend",
        choices=("native", "official", "auto"),
        default="native",
    )
    prepare_parser.add_argument("--png", action="store_true")
    prepare_parser.add_argument("--strict", action="store_true")
    prepare_parser.set_defaults(handler=prepare)

    summary_parser = subparsers.add_parser("summarize", help="aggregate judge JSONL")
    summary_parser.add_argument("--judgments", type=Path, required=True)
    summary_parser.add_argument("--baseline-run")
    summary_parser.add_argument("--candidate-run")
    summary_parser.add_argument("--min-pass-rate", type=float, default=0.9)
    summary_parser.add_argument("--min-overall", type=float, default=4.0)
    summary_parser.add_argument("--max-dimension-regression", type=float, default=0.15)
    summary_parser.add_argument(
        "--require-pairwise",
        action="store_true",
        help="fail promotion when no baseline/candidate pairwise judgments exist",
    )
    summary_parser.add_argument("--output", type=Path)
    summary_parser.set_defaults(handler=summarize)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
