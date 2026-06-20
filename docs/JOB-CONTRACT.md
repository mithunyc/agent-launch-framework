# Managed Job Contract

The managed job contract is the smallest durable unit a future control plane can schedule, audit, retry, or reject.

It is not a scheduler, queue, cloud service, or autonomy grant. It is a receiptable instruction envelope.

## Required Fields

| Field | Purpose |
|---|---|
| `job_id` | Stable id for tracking a run request |
| `agent_pack` | Pack id and version to run |
| `task` | Job kind, prompt, and explicit inputs |
| `runtime` | Adapter, surface, sandbox, and timeout |
| `autonomy_tier` | Maximum authority for the job |
| `policy` | Allowed and blocked actions |
| `workspace` | Disposable, worktree, read-only existing path, or remote |
| `eval_gate` | Required case ids, semantic rubric requirement, and second-opinion requirement before promotion |
| `variance_gate` | Optional repeated-run threshold before packaging or promotion |
| `receipt` | Where proof must be written |

## CTO Rule

No job should graduate to remote/cloud/mobile orchestration unless it has:

1. A job id.
2. A pack version.
3. A runtime adapter.
4. A policy decision.
5. A workspace isolation strategy.
6. A timeout.
7. A receipt target.
8. A rollback statement.
9. Clean-room runtime mode for promotion gates, with user config allowed only for diagnostics.
10. Temporary auth-only `CODEX_HOME` for Codex CLI promotion gates.
11. Semantic rubric requirement for promotion gates.
12. Second-opinion requirement for promotion gates.
13. Repeated-run variance requirement before plugin packaging or provider parity claims.
14. Disposable plugin packaging proof before normal profile install, workspace sharing, CI, cloud, mobile, or provider parity claims.
15. Plugin packaging variance proof before public/repo packaging, CI, cloud, mobile, or provider parity claims.

## Current Example

See `examples/jobs/world-class-reviewer-behavior-gate.job.json`.

This example is A0 read-only. It can validate, run static evals, run Codex behavior evals, run deterministic semantic evals, and write local receipts. It cannot install globally, deploy, touch production data, promote memory, or modify its own skill.

The Codex behavior-gate runtime uses clean-room execution by default: `--ignore-user-config`, `--ignore-rules`, `--disable plugins`, and a temporary `CODEX_HOME` seeded only with `auth.json` when available. This reduces personal-rule, plugin-cache, plugin-sync, and global-skill contamination when a run is used as promotion evidence. It still depends on local Codex authentication and model availability.

`eval_gate.semantic_required=true` means every selected case must pass its hidden `semantic_rubric` after final JSON is produced. This is a deterministic rubric check, not a hosted judge or proof of broad expert reasoning.

`eval_gate.second_opinion_required=true` means every selected case must also pass a deterministic case-independent evaluator for output shape, high-risk verdict alignment, forbidden overclaim boundaries, evidence quality, uncertainty boundaries, risk inventory, rollback, bounded questions, self-grade sanity, and usable recommendation.

See `examples/jobs/world-class-reviewer-variance-gate.job.json` for the next promotion gate. It keeps the same A0 read-only policy but adds `variance_gate`: three runs, zero semantic score drift, zero second-opinion score drift, zero case-status drift, stable safe verdict family, bounded structural count drift, and bounded answer-fingerprint drift. Self-grade drift is recorded but is not promotion authority.

See `examples/jobs/world-class-reviewer-plugin-packaging-gate.job.json` for the disposable plugin packaging gate. It requires the variance gate, generates a local marketplace fixture, validates the plugin package, runs negative plugin fixtures, installs inside a temporary `CODEX_HOME`, and proves prompt-input discovery. The packaging variance runner repeats that gate and compares package/marketplace fingerprints and discovery digests. It still cannot mutate the normal user Codex profile, publish, share, or make remote/mobile/provider claims.
