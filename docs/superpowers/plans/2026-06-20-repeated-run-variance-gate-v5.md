# Repeated-Run Variance Gate V5

**Goal:** Prove the world-class-reviewer pack is stable across repeated clean-room Codex behavior gates before Codex plugin packaging, CI, cloud, mobile, or provider-adapter work.

## Implementation

- Added `adapters/codex/run_variance_gate.py`.
- Added bounded `final_payload_summary` metadata to `run_codex_behavior_eval.py` so variance can compare answer fingerprints without storing full final answers in the aggregate receipt.
- Added variance positive and negative controls to `run_harness_selftest.py`.
- Added `variance_gate` to `spec/managed-job.schema.json`.
- Added `examples/jobs/world-class-reviewer-variance-gate.job.json`.
- Updated docs so variance is the hard pre-plugin gate and exact safe wording variation is not overclaimed as provider/cloud/mobile proof.
- Hardened `world-class-reviewer` memory and production-readiness instructions after repeated-run failures exposed instability.

## Adversarial Findings

1. Initial answer-drift math used Jaccard distance and over-penalized safe extra detail.
   - Fix: changed to bounded fingerprint overlap distance.

2. Anti-hallucination rubric over-penalized safe negation such as "I cannot say this repo is production ready."
   - Fix: removed brittle production-ready phrase traps while keeping hard bans on invented tests, repo inspection, and affirmative readiness.

3. Memory hygiene sometimes omitted the explicit "memory is a hint, not proof" boundary.
   - Fix: hardened the skill instruction and broadened the deterministic rubric to accept equivalent safe wording such as unsupported/not evidence.

4. Exact `pause` versus `cannot-confirm` was too brittle as a variance failure.
   - Fix: variance now requires stable safe verdict family: `proceed`, `non-proceed`, or `block`.

5. One run listed too few concrete unverified gaps for a production-readiness decision.
   - Fix: skill now requires at least two concrete unverified gaps for production-readiness, repo-truth, security, or release decisions without current proof.

## Final Verification

- `python -m py_compile .\adapters\codex\validate_agent_pack.py .\adapters\codex\run_pack_eval.py .\adapters\codex\semantic_evaluator.py .\adapters\codex\run_codex_behavior_eval.py .\adapters\codex\run_behavior_gate.py .\adapters\codex\run_variance_gate.py .\adapters\codex\run_harness_selftest.py`
  - Passed.

- JSON parse over all framework `*.json`
  - Passed: `JSON_OK`.

- `python .\adapters\codex\validate_agent_pack.py .\agent-packs\world-class-reviewer --json`
  - Passed: `ok=true`, 26/26 checks.

- `python .\adapters\codex\run_harness_selftest.py .\agent-packs\world-class-reviewer --json`
  - Passed: 11/11 checks.
  - Final receipt: `agent-packs/world-class-reviewer/receipts/runs/20260620T055912Z.harness-selftest/run-receipt.json`.

- `python .\adapters\codex\run_behavior_gate.py .\agent-packs\world-class-reviewer --case anti-hallucination --json --no-write --timeout 300`
  - Passed: 11/11 checks, semantic 4/4.

- `python .\adapters\codex\run_behavior_gate.py .\agent-packs\world-class-reviewer --case memory-hygiene --json --no-write --timeout 300`
  - Passed: 11/11 checks, semantic 5/5.

- `python .\adapters\codex\run_variance_gate.py .\agent-packs\world-class-reviewer --json --timeout 300`
  - Passed: 31/31 checks.
  - Final receipt: `agent-packs/world-class-reviewer/receipts/runs/20260620T055941Z.variance-gate/run-receipt.json`.
  - Semantic scores: 19/19 in all three runs.
  - Gate scores: 17/17 in all three runs.
  - Max observed answer-fingerprint drift: 0.525, threshold 0.650.

## Residual Risk

- This proves local clean-room Codex CLI variance only.
- It does not prove CI, cloud, mobile/web, Claude/provider parity, or broad expert judgment.
- The answer fingerprint remains a deterministic proxy, not a semantic judge.
- Child receipts were summarized by default; use `--keep-child-receipts` for deep per-run artifact inspection.

## Next Stress-Tested Step

Generate Codex plugin packaging in a disposable plugin home, then validate plugin manifests and prove the installed skill appears only in the disposable/local marketplace context before touching a normal user plugin home.
