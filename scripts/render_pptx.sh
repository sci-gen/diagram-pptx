#!/usr/bin/env bash
set -euo pipefail

input="${1:?usage: render_pptx.sh INPUT.pptx OUTPUT_DIR}"
output_dir="${2:?usage: render_pptx.sh INPUT.pptx OUTPUT_DIR}"

mkdir -p "$output_dir"
profile_dir="$(mktemp -d)"
trap 'rm -rf "$profile_dir"' EXIT

libreoffice \
  --headless \
  "-env:UserInstallation=file://$profile_dir" \
  --convert-to pdf \
  --outdir "$output_dir" \
  "$input"

pdf="$output_dir/$(basename "${input%.pptx}").pdf"
pdftoppm -png -r 144 -singlefile "$pdf" "$output_dir/slide-1"
