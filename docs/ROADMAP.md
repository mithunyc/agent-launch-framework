# Roadmap

## V0: Agent Pack Foundation

- Canonical pack layout.
- Codex skill installer and uninstaller.
- Validator.
- Local eval runner.
- Demo world-class reviewer pack.
- Receipt template.
- Safety, memory, and self-improvement docs.

## V1: Codex Runner

- `codex exec` runner with JSONL capture.
- Output schema support.
- Receipt generation from real runs.
- Cost/time/check summaries.
- Pack-level policy enforcement before execution.
- Disposable repo-scoped `.agents/skills` workspace for behavior evals without global install.
- Mechanical behavioral baitset checks before semantic evaluator work.

## V1.5: Managed Behavior Gate

- Managed job contract schema.
- Example read-only behavior-gate job.
- Aggregate behavior gate receipt.
- Static eval plus all Codex behavior cases by default.
- Explicit policy decision and rollback in gate receipts.

## V1.6: Clean-Room And Harness Self-Test

- Clean-room Codex behavior gates with user config/rules suppressed and temporary auth-only `CODEX_HOME` by default.
- Diagnostic user-config mode clearly separated from promotion evidence.
- Deterministic negative fixture self-tests for broken skills, missing evals, unsafe claims, and malformed jobs.
- Receipts for harness self-tests.

## V1.7: Hidden Semantic Rubrics

- Case-level `semantic_rubric` metadata stored outside prompts.
- Deterministic semantic evaluator for final structured JSON.
- Behavior and managed-gate receipts include semantic scores.
- Harness self-tests include known-good and known-bad semantic outputs.

## V1.8: Repeated-Run Variance Gate

- Behavior case receipts include bounded answer fingerprints for drift checks.
- Variance gate runs the full behavior gate three times by default.
- Gate requires stable semantic scores, stable second-opinion scores, stable case statuses, stable safe verdict families, bounded structural count drift, and bounded answer-fingerprint drift.
- Self-grade drift is recorded as telemetry, not trusted as a promotion authority.
- Harness self-tests include known-good and known-bad variance controls.

## V1.9: Disposable Plugin Packaging Gate

- Pack fingerprints bind variance receipts to current canonical pack content.
- Pack-to-plugin generator creates `.codex-plugin/plugin.json`, skill copies, runtime-safe pack references, and repo-local marketplace metadata.
- Plugin validator checks manifest shape, source path safety, policy fields, semver, skill frontmatter, and expected skill discovery.
- Packaging gate proves a temp-`CODEX_HOME` marketplace add, plugin install, plugin list, and `codex debug prompt-input` skill visibility.
- Negative plugin fixtures prove missing manifest, unsafe marketplace path, and broken skill frontmatter fail.

## V1.10: Second Opinion And Packaging Variance

- Deterministic second-opinion evaluator grades generic safety and usefulness invariants independently from case rubrics.
- Behavior and variance gates require second-opinion pass and zero second-opinion score drift.
- Packaging generator emits deterministic package and marketplace fingerprints.
- Packaging variance gate repeats disposable plugin packaging and compares package fingerprints, marketplace fingerprints, CLI behavior, and prompt-input discovery digests.
- Public/repo marketplace packaging remains blocked until disposable packaging variance stays stable and repository wiring is explicit.

## V2: Public Packaging And Remote Proof

- Wire the local folder to `mithunyc/agent-launch-framework` without accidentally pushing parent `titan-research` state.
- Add GitHub Actions with dependency-free static gates and an authenticated full Codex gate.
- Require the full Codex gate to pass in CI before treating the repo as remote proof.
- Add public/repo marketplace packaging only after the disposable gate survives repeated local and CI runs.
- Validate plugin manifests against local Codex expectations and official plugin docs.
- Prove CI or remote execution before making mobile/web autonomy claims.

## V3: Remote And Cloud Runtime

- GitHub Action runner.
- Codex cloud adapter where available.
- Remote-control host adapter for mobile steering.
- Clear offline/host-online capability labels.
- Managed-agent control-plane spike with job registry, policy decisions, receipt store, and runtime adapter contracts.

## V4: Governed Memory And Learning

- Memory proposal queue.
- Evidence-based memory promotion.
- Expiry and drift checks.
- Eval-gated skill improvement pipeline.
