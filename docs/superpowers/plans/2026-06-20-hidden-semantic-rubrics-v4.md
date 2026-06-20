# Hidden Semantic Rubrics V4

**Goal:** Move the framework beyond mechanical text checks by adding deterministic hidden semantic grading before plugin, CI, cloud, mobile, or provider-adapter work.

**Architecture:** Keep eval cases provider-neutral. Store hidden `semantic_rubric` metadata in `agent-packs/*/evals/cases/*.json`, do not include those rubric details in the Codex prompt, and grade final structured JSON inside the Codex adapter after `codex exec` returns.

## Implementation

- Added `adapters/codex/semantic_evaluator.py`.
- Added `semantic_rubric` criteria to all `world-class-reviewer` eval cases.
- Updated `validate_agent_pack.py` so rubrics are required and structurally checked.
- Updated `run_pack_eval.py` so static eval evidence counts semantic criteria.
- Updated `run_codex_behavior_eval.py` so behavior case status includes semantic checks and aggregate semantic score.
- Updated `run_behavior_gate.py` so managed gate jobs require semantic evaluation and receipts expose semantic pass/fail evidence.
- Updated `run_harness_selftest.py` with missing-rubric, known-good semantic output, and known-bad semantic output controls.
- Added `spec/eval-case.schema.json`.
- Updated docs and the `world-class-reviewer` skill memory rule.

## Adversarial Findings

- The first anti-hallucination smoke failed because the old mechanical forbidden phrase `tests passed` punished a valid sentence saying tests could not be confirmed. The check now forbids affirmative success claims such as `all tests passed` and `tests passed successfully`.
- The first semantic smoke failed because `production ready` was too broad and punished a valid refusal to declare production readiness. The rubric now forbids affirmative readiness claims.
- The first full gate failed because memory metadata appeared in an evidence item instead of the recommendation. The rubric now accepts source/confidence/expiry/reason in auditable evidence, and the skill now states the memory proposal rule directly.

## Verification Evidence

- `python -m py_compile ...` passed for all Codex adapter Python files.
- Framework JSON parse passed with `JSON_OK`.
- `validate_agent_pack.py --json` returned `ok: true`, 26/26 checks.
- `run_pack_eval.py --json --no-write` returned `ok: true`, 5/5 checks and 19 semantic criteria.
- `run_harness_selftest.py --json` returned `ok: true`, 9/9 checks.
- Single-case clean-room behavior gate for `anti-hallucination` returned `ok: true`, 11/11 checks and semantic 4/4.
- Full clean-room behavior gate returned `ok: true`, 17/17 gate checks and semantic 19/19.

## Final Receipts

- Harness self-test: `agent-packs/world-class-reviewer/receipts/runs/20260620T052701Z.harness-selftest/run-receipt.json`
- Full behavior gate: `agent-packs/world-class-reviewer/receipts/runs/20260620T052708Z.behavior-gate/run-receipt.json`
- Child behavior eval: `agent-packs/world-class-reviewer/receipts/runs/20260620T052708Z.behavior-eval/run-receipt.json`

## Residual Risk

- This is deterministic semantic grading, not broad expert judgment.
- The pass is local Codex CLI evidence, not cloud/mobile/web managed execution.
- Repeated-run variance is not proven yet.
- A model-judge or human-review layer should be added only after deterministic rubrics remain stable across repeated runs.
