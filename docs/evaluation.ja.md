# 評価・改善ループ

スライド向けMermaid生成Skillは、Mermaid parserとは別のagent policyです。
パッケージの正確性テストとは分離して評価します。

## 評価レイヤー

1. **決定論的gate**：parse、render、diagram数、semantic element数、
   scene aspect ratio、diagnostic、元source保持を検査します。
2. **Multimodal LLM judge**：16:9のrender結果を、要件忠実性、可読性、
   typography、visual balance、情報粒度、構造の凝集性、分割品質で採点します。
3. **匿名pairwise比較**：現行Skillと改善候補をA/B比較します。A/Bの表示順を
   反転した判定も必ず実施します。
4. **人間による監査**：regressionとjudge不一致を全件確認し、それ以外の
   pass caseも最低10%を抜き取り確認します。

LLM判定は証拠であって正解そのものではありません。人間が採点した小規模な
holdout setを保持し、Judgeとの一致度を定期的に確認します。

## 同梱物

- `evals/cases/slide-authoring-v1.jsonl`：日英のbrief、control、
  過密diagram、font overflow、自然な分割case
- `evals/candidates/reference-v1.jsonl`：全同梱caseのreview済みreference回答
- `evals/results/reference-v1-summary.json`：初回package比較とpromotion gate結果
- `evals/prompts/judge-v1.md`：provider-neutralな画像付きJudge指示
- `evals/schemas/case-v1.schema.json`：評価case contract
- `evals/schemas/candidate-v1.schema.json`：生成結果contract
- `evals/schemas/judgment-v1.schema.json`：score／pairwise判定contract
- `scripts/authoring_eval.py`：決定論的準備と集計

特定providerのSDKは外部adapterへ置きます。repository側をJSON／JSONLに
固定することで、OpenAI、Anthropic、Google、local model、人間の入力formを
同じ判定形式へ接続できます。

## 評価の実行

caseごとにcandidate JSONLを生成します。

```json
{"schema_version":1,"case_id":"flow-linear-release","run_id":"skill-v1","candidate_id":"flow-linear-release-1","generator":{"provider":"example","model":"example-model","skill_version":"v1","prompt_version":"v1"},"diagrams":[{"title":"Release flow","source":"flowchart LR\nA[Intake] --> B[Review] --> C[Build] --> D[Verify] --> E[Release]"}]}
```

決定論的metrics、図単体SVG、1600×900のslide preview SVGを生成します。

```bash
python scripts/authoring_eval.py prepare \
  --candidates artifacts/evals/skill-v1.jsonl \
  --output-dir artifacts/evals/skill-v1
```

`diagram-pptx[image]`がある場合は`--png`も指定でき、同じ16:9 previewを
rasterizeします。生成された`judge-items.jsonl`、render画像、Judge promptを
外部adapterへ渡し、同梱Schemaに一致するJSON判定を保存します。

baselineとcandidateを集計します。

```bash
python scripts/authoring_eval.py summarize \
  --judgments artifacts/evals/judgments.jsonl \
  --baseline-run skill-v1 \
  --candidate-run skill-v2 \
  --require-pairwise \
  --output artifacts/evals/summary.json
```

2026-07-28の初回reference runでは、固定Docker環境で14 caseをすべて
renderしました。PyPI `0.1.0b2`と`0.1.0b3`候補はいずれも14/14 caseがpass、
平均4.55/5、hard failure 0件でした。表示順を反転した28回のpairwise判定は
すべて実用上tieとなり、候補はno-regression promotion gateを通過しました。
これは再現可能な開始点であり、独立したuser feedbackの代替ではありません。

## Promotion gate

初期値は厳しめですが調整可能です。

- 決定論的／Judge hard failureが0件
- holdout pass率90%以上
- rubric平均4.0/5以上
- 各rubric dimensionの低下が0.15以内
- A/B順序反転後もpairwiseの勝数が敗数以上（比較がある場合、または
  `--require-pairwise`指定時）
- regression、不一致、無作為抽出pass caseを人間が確認

有料かつ非決定論的なJudgeをすべてのpackage PRでは実行しません。
決定論的validationはCIで実行し、Skill、rubric、layout policy、関連rendererを
変更したときにLLM judgeを実行します。

## 改善サイクル

1. 匿名化した実障害と意図的に難しいsynthetic caseを追加する。
2. development setとholdout setを固定する。
3. promptとmodelを固定してbaseline／candidateを生成する。
4. 決定論的gate、render、匿名A/B Judge、人間監査を実施する。
5. rubric dimensionとhard-failure labelで失敗を分類する。
6. 1回のiterationではpolicyまたはrendererの変更を1種類に絞る。
7. holdoutとpairwise gateを通過した場合だけ改善版を採用する。
8. Skill、prompt、judge model、rubric、case setのversionを記録する。

GitHubのdiagram feedback formから、公開可能な実例を任意提供してもらいます。
機密Mermaidは要求せず、sourceと画像を必ず匿名化してから投稿してもらいます。

## 設計上の参考資料

固定anchorによる採点、人間との一致、LLM judgeの既知のbiasについて、
以下を設計の参考にしています。

- [G-Eval](https://arxiv.org/abs/2303.16634)
- [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena](https://arxiv.org/abs/2306.05685)
- [Position Bias in LLM-based Evaluation](https://arxiv.org/abs/2406.07791)
- [OpenAI: Evals drive the next chapter of AI](https://openai.com/index/evals-drive-next-chapter-of-ai/)
