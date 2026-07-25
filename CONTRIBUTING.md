# Contributing

Development is containerized:

```bash
docker compose run --build --rm test
```

Before opening a pull request:

1. Add semantic tests for importer or layout changes.
2. Add package/XML tests for renderer changes.
3. Run the example renderer and inspect `artifacts/rendered/slide-1.png`.
4. Keep Mermaid-specific logic under `importers/mermaid.py`.
5. Keep python-pptx/Open XML details under `render/python_pptx.py`.

New diagram syntaxes should normally be importers that target the existing IR.
If a syntax has a fundamentally different semantic model, propose a sibling
model rather than adding unrelated optional fields to `Diagram`.
