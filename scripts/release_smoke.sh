#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
release_dir="$(mktemp -d)"
smoke_venv="$(mktemp -d)"
smoke_workdir="$(mktemp -d)"

cleanup() {
  rm -rf "$release_dir" "$smoke_venv" "$smoke_workdir"
}
trap cleanup EXIT

cd "$root_dir"

ruff check .
ruff format --check .
python -m build --outdir "$release_dir"
twine check "$release_dir"/*

python -m venv "$smoke_venv"
"$smoke_venv/bin/python" -m pip install \
  --quiet \
  --no-cache-dir \
  "$release_dir"/diagram_pptx-*.whl

cd "$smoke_workdir"

"$smoke_venv/bin/python" - <<'PY'
import importlib.metadata as metadata
import importlib.resources as resources

import diagram_pptx

distribution = metadata.distribution("diagram-pptx")
assert distribution.version == "0.1.0a1"
assert distribution.metadata["License-Expression"] == "MIT"
assert any(
    str(path).endswith(".dist-info/licenses/LICENSE")
    for path in (distribution.files or ())
)

package_root = resources.files("diagram_pptx")
assert package_root.joinpath("py.typed").is_file()
assert package_root.joinpath("schemas/diagram-v1.json").is_file()
assert package_root.joinpath("schemas/theme-v1.json").is_file()

print("wheel import, metadata, and package resources: OK")
PY

"$smoke_venv/bin/diagram-pptx" \
  inspect "$root_dir/examples/flowchart.mmd" --json \
  > inspect.json
"$smoke_venv/bin/diagram-pptx" \
  render "$root_dir/examples/flowchart.mmd" wheel-smoke.pptx \
  --backend native
test -s wheel-smoke.pptx
"$smoke_venv/bin/diagram-pptx" doctor

echo "clean wheel smoke test: OK"
