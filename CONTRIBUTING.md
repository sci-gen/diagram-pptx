# Contributing

Development and visual verification are containerized:

```bash
docker compose run --build --rm test
docker compose run --build --rm official-test
docker compose run --build --rm example
```

Before opening a pull request:

1. Run `ruff check .` and `ruff format --check .`.
2. Add parse/serialize/JSON tests for semantic changes.
3. Verify deterministic bounds and completeness for layout changes.
4. Verify saved/reopened OOXML and absence of whole-diagram image embedding
   for renderer changes.
5. Inspect the five PNGs under `artifacts/rendered`.
6. Run `docker compose run --rm test bash scripts/release_smoke.sh`.

Keep dependencies one-way:

- Mermaid grammar and source diagnostics: `mermaid.py` / `importers`
- typed meaning: `model.py`
- positioned backend-neutral primitives: `scene.py`
- geometry: `layout`
- theme precedence: `styles.py`
- PowerPoint/OOXML details: `render/python_pptx.py`

New syntaxes should target an existing semantic model when appropriate.
Semantically different diagram families receive a sibling model and a
DrawingScene layout adapter; do not accumulate unrelated optional fields in a
generic graph.

## Release checklist

1. Move all user-visible changes into the versioned CHANGELOG section and
   leave `Unreleased` empty.
2. Run the Native, Official, and clean-wheel checks:

   ```bash
   docker compose run --build --rm test
   docker compose run --rm official-test
   docker compose run --rm test bash scripts/release_smoke.sh
   ```

3. Push the release commit and wait for every GitHub Actions job to pass.
4. Configure the `testpypi` trusted-publishing environment once, then run
   **Test publish to TestPyPI** manually and install that exact version from
   TestPyPI:

   ```bash
   python -m pip install \
     --index-url https://test.pypi.org/simple/ \
     --extra-index-url https://pypi.org/simple/ \
     diagram-pptx==X.Y.Z
   ```

5. Configure the `pypi` trusted-publishing environment once, create the
   `vX.Y.Z` GitHub release, and verify the package from PyPI in a fresh
   environment.
