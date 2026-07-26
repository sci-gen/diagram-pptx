"""Detect large visual regressions in fixed-container slide renderings."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageStat


def difference(actual: Path, expected: Path) -> float:
    with Image.open(actual) as actual_image, Image.open(expected) as expected_image:
        actual_rgb = actual_image.convert("RGB")
        expected_rgb = expected_image.convert("RGB")
        if actual_rgb.size != expected_rgb.size:
            actual_rgb = actual_rgb.resize(expected_rgb.size)
        diff = ImageChops.difference(actual_rgb, expected_rgb)
        channel_means = ImageStat.Stat(diff).mean
        return sum(channel_means) / (len(channel_means) * 255)


def main() -> int:
    actual_dir = Path(sys.argv[1])
    golden_dir = Path(sys.argv[2])
    threshold = float(sys.argv[3]) if len(sys.argv) > 3 else 0.08
    failures: list[str] = []
    golden_files = sorted(golden_dir.glob("slide-*.png"))
    if not golden_files:
        print(f"No golden PNGs found in {golden_dir}", file=sys.stderr)
        return 2
    for expected in golden_files:
        actual = actual_dir / expected.name
        if not actual.is_file():
            failures.append(f"{expected.name}: missing")
            continue
        score = difference(actual, expected)
        print(f"{expected.name}: normalized pixel difference {score:.4f}")
        if score > threshold:
            failures.append(f"{expected.name}: {score:.4f} > {threshold:.4f}")
    if failures:
        print("Large visual regressions detected:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
