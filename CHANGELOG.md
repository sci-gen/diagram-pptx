# Changelog

All notable changes follow
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and Semantic
Versioning.

## [Unreleased]

### Added

- A provider-neutral LLM-as-a-judge evaluation kit for 16:9 Mermaid
  authoring, including bilingual guidance, mixed Japanese/English cases,
  deterministic rendering metrics, JSON contracts, pairwise judgments, and a
  public feedback form.
- Pre-render text fitting that preserves intentional per-element font-size
  differences, plus Yu Gothic as the default Japanese PowerPoint typeface.

## [0.1.0b2] - 2026-07-27

### Changed

- Updated the GitHub Actions workflow runtime dependencies to their Node.js
  24-based major releases.

### Fixed

- Converted Mermaid Timeline cards emitted as SVG paths into standard rounded
  PowerPoint AutoShapes so labels remain vertically centered in LibreOffice
  and other OOXML renderers while staying directly editable on each shape.

## [0.1.0b1] - 2026-07-27

### Added

- Matplotlib-like `save()`, `to_svg()`, `to_png()`, and `to_jpeg()` methods on
  parsed Mermaid documents and all typed diagram models.
- A self-contained SVG renderer and optional high-DPI PNG/JPEG export through
  the `image` extra.
- The `all` aggregate extra for every optional runtime feature.
- JSON-safe `SceneResult` and `ExportResult` operation summaries.
- A shared `label_background` option for connector and message labels in
  PowerPoint, SVG, PNG, JPEG, and the CLI.
- A bilingual user guide and a generated quick-start diagram preview.
- A Mermaid 11.16 registry covering all 30 documented syntax families plus
  the bundled experimental Railroad family.
- Lossless `MermaidSourceDiagram` passthrough and pinned Official integration
  fixtures for all 31 registered families.
- A machine-readable `diagram-pptx support --json` compatibility command and
  bilingual statement-level compatibility documentation.
- A bilingual `examples/` index with Mermaid sources, PNG previews, and a
  31-slide editable-shape PPTX covering every registered Mermaid family.
- Unit-aware manual font sizes in points, CSS pixels, or a fraction of slide
  height, with bare numeric values defaulting to points.
- Reusable `DiagramSettings`, `TypographySettings`, and `DiagramCompiler`
  instances for deck-wide defaults without process-global configuration.
- A versioned JSON Schema for compiler settings.

### Changed

- PowerPoint and image output now share the same public `build_scene()` stage,
  including backend selection, style resolution, themes, and color maps.
- Missing Mermaid CLI errors now explain the Node.js/npm prerequisite;
  `backend="auto"` records an informational Native-fallback diagnostic.
- Opaque custom label backgrounds automatically select light or dark text
  unless an explicit element or color-map text color is supplied.
- Official SVG import now resolves `currentColor`, approximates gradients with
  a usable stop color, and sanitizes invalid generated paint values.
- Official SVG import now preserves elliptical arc geometry and per-paint
  opacity, improving Venn diagrams and other curved translucent shapes.
- Official SVG import now preserves nested viewport transforms, DOM paint
  order, rotated primitives and text, text anchors/baselines, multiline
  tspans, inherited presentation attributes, and selector-aware CSS styling.
- Official Radar output now enlarges axis labels, legends, and chart titles
  for presentation-scale readability.
- Shape labels now use adaptive typography with up to two-thirds of the
  available height, constrained by text width, line count, neighboring labels,
  and shape-specific padding.
- Official Kanban card labels now live directly in each editable card
  AutoShape instead of overlapping standalone text boxes.
- Official Radar output now uses a smaller plot radius with larger axis,
  legend, and title typography.
- Official Quadrant output now compacts the plot area and sizes point, axis,
  and chart labels relative to the diagram's short side.
- Official Sankey output now stacks node names and values on separate lines
  and scales their typography relative to the complete diagram.
- Official User Journey section and task labels now live directly in their
  editable AutoShapes, with duplicate SVG fallback labels removed.
- Official Timeline year and event labels now live directly in their
  editable AutoShapes and remain vertically centered after scaling.
- PowerPoint edge and sequence-message labels now keep a presentation-safe
  12-point minimum, with their text boxes expanded around the original anchor.
- Explicit typography follows settings, theme role, source element, theme
  class/ID, and compile-time override precedence; automatic fitting remains
  the default and can be disabled per compiler instance.

## [0.1.0a1] - 2026-07-26

### Added

- Mutable typed models for Flow, Sequence, Class, ER, and State diagrams.
- Mermaid frontend with diagnostics, strict mode, canonical serialization,
  unsupported-statement preservation, and partial-model mutation protection.
- Versioned model and theme JSON schemas.
- Renderer-neutral `DrawingScene` and deterministic Pure Python layouts for
  all five families.
- Official Mermaid CLI backend pinned to 11.16.0 in Docker, with safe process
  execution and Mermaid-specific SVG geometry import.
- Typed styles, PowerPoint theme colors, RGBA opacity, class/ID rules, three
  source-style policies, and final color maps.
- Editable native AutoShapes/connectors/text with a single top-level
  PowerPoint group and semantic child names.
- `render`, `inspect`, and `doctor` CLI commands.
- Python 3.10–3.13 Native CI, Docker Official integration tests, package
  validation, and PPTX→PDF→PNG visual artifacts.
- Independent `style="native"|"official"` presets and continuous `jet`,
  `viridis`, `plasma`, and `magma` color-map sampling by visual channel.
- `primary`/`secondary` color-map shorthand and automatic per-node
  light/dark text contrast when `text` is omitted.
- Same-slide placement through `full`, `left`, `right`, `top`, and `bottom`
  presets or normalized top-left-origin `relative_bounds`.
- Typed `colors` configuration, a `py.typed` marker, expanded public
  docstrings, and a JSON-safe `CompileResult.to_dict()` for external adapters.
- Explicit separation of vendor-specific tool and plugin adapters from the
  provider-neutral core package.
- MCP server, Codex plugin manifest, and agent skill integration examples,
  with typed adapter signatures as the tool-schema boundary.
- Grouped Native Sequence stick actors and duration-aware nested activation
  bars, including inline Mermaid activation markers.
- Native Class namespace containers with canonical namespace serialization.
- Composite State boundary connectors and hierarchical nested PowerPoint
  groups.

### Changed

- Native is now the default backend; `auto` and `official` remain explicit
  geometry choices.

### Fixed

- Removed inherited Office theme shadows/effects from generated shapes and
  connectors.
- Increased standard arrowheads to a visible medium size and compacted edge
  label backgrounds so they do not hide most of short connectors.
- Moved labels off short connector segments automatically so return paths and
  arrowheads remain visible.
- Reduced the default corner radius of dashed visual containers.
- Corrected Native Sequence return-message dashes and label placement, Class
  association arrowheads, and State start/end pseudo-state rendering.

[Unreleased]: https://github.com/sci-gen/diagram-pptx/compare/v0.1.0b2...HEAD
[0.1.0b2]: https://github.com/sci-gen/diagram-pptx/releases/tag/v0.1.0b2
[0.1.0b1]: https://github.com/sci-gen/diagram-pptx/releases/tag/v0.1.0b1
[0.1.0a1]: https://github.com/sci-gen/diagram-pptx/releases/tag/v0.1.0a1
