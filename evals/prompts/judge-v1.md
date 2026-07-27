# Mermaid slide-authoring judge v1

Evaluate whether an LLM-authored Mermaid deliverable works as an editable
diagram on a 16:9 presentation slide.

Inputs:

- `case`: the brief, required concepts, slide region, and split expectation;
- `candidate`: one or more Mermaid sources and deterministic metrics;
- `renders`: the corresponding 16:9 render images;
- optionally, blind candidates `A` and `B` for pairwise comparison.

Judge the rendered deliverable first. Use Mermaid source and metrics to explain
the visual result, not as a substitute for inspecting it. Do not reward a
candidate for being longer, more detailed, or stylistically elaborate.

## Score dimensions

Return an integer from 1 to 5 for every dimension.

- `requirement_fidelity`: preserves the brief's meaning and required concepts.
- `slide_readability`: readable at normal slide scale without tiny, clipped,
  overlapping, or unexpectedly wrapped text.
- `typography_quality`: uses legible fonts, intentional hierarchy, and
  consistent sizes for peer elements. Penalize accidental size variation,
  text escaping its shape, and unsuitable Japanese font fallback.
- `visual_balance`: uses the requested 16:9 region without becoming extremely
  wide, tall, sparse, or visually lopsided.
- `information_granularity`: shows audience-meaningful steps and omits
  implementation microsteps that do not advance the slide's message.
- `structural_cohesion`: keeps tightly connected loops and decisions together
  while maintaining an understandable reading order.
- `split_quality`: chooses an appropriate number of diagrams and, when split,
  cuts at weakly coupled boundaries with explicit cross-diagram continuity.

Anchors:

- `5`: presentation-ready; no meaningful correction required.
- `4`: good; one minor correction would improve it.
- `3`: usable only after a visible or structural correction.
- `2`: major redesign required.
- `1`: failed or materially misleading.

## Hard failures

Use only these stable labels:

- `invalid_or_missing_render`
- `missing_required_content`
- `unreadable_text`
- `overlap_or_clipping`
- `extreme_aspect_ratio`
- `excessive_detail`
- `incoherent_split`
- `unauthorized_source_change`

Set `verdict` to `fail` when a hard failure applies, when either
`requirement_fidelity` or `slide_readability` is below 3, or when the
deliverable cannot be used on the requested slide without redesign.

For pairwise evaluation:

1. Treat labels `A` and `B` as anonymous.
2. Score both independently before choosing a winner.
3. Prefer `tie` when the practical difference is negligible.
4. The harness must repeat the comparison with reversed presentation order.

Return JSON only, matching `evals/schemas/judgment-v1.schema.json`. Keep the
rationale concise and actionable. Do not include hidden chain-of-thought.
