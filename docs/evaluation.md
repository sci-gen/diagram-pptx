# Evaluation and improvement loop

The slide-authoring Skill is an agent policy, not part of the Mermaid parser.
Evaluate it separately from package correctness.

## Evaluation layers

1. **Deterministic gates** check parsing, rendering, diagram count, semantic
   element count, scene aspect ratio, diagnostics, and source preservation.
2. **Multimodal LLM judges** score the rendered 16:9 result against an anchored
  rubric for meaning, readability, typography, balance, granularity,
  cohesion, and split quality.
3. **Blind pairwise comparison** compares the current Skill with a candidate
   Skill. Repeat every comparison with `A` and `B` reversed.
4. **Human audit** reviews all regressions and judge disagreements plus at
   least 10% of otherwise passing cases.

LLM judgments are evidence, not ground truth. Keep a small human-calibrated
holdout set and periodically measure judge agreement against it.

## Repository assets

- `evals/cases/slide-authoring-v1.jsonl`: mixed English/Japanese briefs,
  controls, density failures, typography/overflow cases, and natural splits.
- `evals/candidates/reference-v1.jsonl`: reviewed reference answers for every
  bundled case.
- `evals/results/reference-v1-summary.json`: the first package comparison and
  promotion-gate result.
- `evals/prompts/judge-v1.md`: provider-neutral multimodal judge instructions.
- `evals/schemas/case-v1.schema.json`: evaluation-case contract.
- `evals/schemas/candidate-v1.schema.json`: generator output contract.
- `evals/schemas/judgment-v1.schema.json`: score and pairwise result contract.
- `scripts/authoring_eval.py`: deterministic preparation and aggregation.

Keep provider SDKs in an external adapter. The repository contracts remain
plain JSON/JSONL so OpenAI, Anthropic, Google, local models, or a human form can
produce the same judgment records.

## Run an evaluation

Generate one candidate JSONL record per case:

```json
{"schema_version":1,"case_id":"flow-linear-release","run_id":"skill-v1","candidate_id":"flow-linear-release-1","generator":{"provider":"example","model":"example-model","skill_version":"v1","prompt_version":"v1"},"diagrams":[{"title":"Release flow","source":"flowchart LR\nA[Intake] --> B[Review] --> C[Build] --> D[Verify] --> E[Release]"}]}
```

Prepare deterministic metrics, diagram SVGs, and 1600×900 slide-preview SVGs:

```bash
python scripts/authoring_eval.py prepare \
  --candidates artifacts/evals/skill-v1.jsonl \
  --output-dir artifacts/evals/skill-v1
```

Add `--png` when `diagram-pptx[image]` is installed to rasterize the same
16:9 preview. Send each generated `judge-items.jsonl` record, its render
files, and the judge prompt to the chosen adapter. Write JSON judgments
matching the bundled schema.

Aggregate a baseline and candidate:

```bash
python scripts/authoring_eval.py summarize \
  --judgments artifacts/evals/judgments.jsonl \
  --baseline-run skill-v1 \
  --candidate-run skill-v2 \
  --require-pairwise \
  --output artifacts/evals/summary.json
```

The initial reference run on 2026-07-28 rendered all 14 cases in the same
pinned Docker environment. Both PyPI `0.1.0b2` and the `0.1.0b3` candidate
passed 14/14 cases with a mean score of 4.55/5 and no hard failures. All 28
order-reversed pairwise judgments were practical ties, so the candidate
cleared the no-regression promotion gate. Treat this as a reproducible
starting point, not a substitute for independent user feedback.

## Promotion gate

Initial defaults are intentionally strict but adjustable:

- no deterministic or judged hard failures;
- holdout pass rate at least 90%;
- mean rubric score at least 4.0/5;
- no rubric dimension regresses by more than 0.15;
- pairwise wins are not lower than losses after order reversal (enforced when
  comparisons are present, or required with `--require-pairwise`);
- a human reviews regressions, disagreements, and a random passing sample.

Do not run paid or nondeterministic judges on every package PR. Run the
deterministic validation in CI, and run LLM judging when the Skill, rubric,
layout policy, or a relevant renderer changes.

## Improvement cycle

1. Add sanitized real failures and deliberately difficult synthetic cases.
2. Freeze a development set and a holdout set.
3. Generate baseline and candidate outputs with pinned prompts and models.
4. Run deterministic gates, render, blind A/B judging, and human audit.
5. Classify failures by rubric dimension and hard-failure label.
6. Change one policy or renderer behavior at a time.
7. Promote only after holdout and pairwise gates pass.
8. Record the Skill, prompt, judge model, rubric, and case-set versions.

Use the GitHub diagram-feedback issue form to collect opt-in examples. Never
request confidential Mermaid; contributors should sanitize sources and images
before posting them publicly.

## Design references

The rubric and controls follow published guidance on anchored scoring,
judge/human agreement, and known LLM-judge biases:

- [G-Eval](https://arxiv.org/abs/2303.16634)
- [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena](https://arxiv.org/abs/2306.05685)
- [Position Bias in LLM-based Evaluation](https://arxiv.org/abs/2406.07791)
- [OpenAI: Evals drive the next chapter of AI](https://openai.com/index/evals-drive-next-chapter-of-ai/)
