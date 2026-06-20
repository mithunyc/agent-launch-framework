# Behavior Gate And Job Contract V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the one-case Codex behavior proof into a repeatable managed-agent gate with a job contract and aggregate receipt.

**Architecture:** Keep the agent pack as the canonical source. Add a portable managed-job schema that names the pack, runtime, autonomy tier, policy, workspace strategy, eval gate, timeout, and receipt target. Add a Codex adapter gate that runs static pack evals plus Codex behavior evals and emits a single receipt suitable for a future control plane.

**Tech Stack:** Python standard library, existing Codex adapter scripts, JSON Schema, Markdown docs.

---

### Task 1: Managed Job Contract

**Files:**
- Create: `spec/managed-job.schema.json`
- Create: `examples/jobs/world-class-reviewer-behavior-gate.job.json`
- Create: `docs/JOB-CONTRACT.md`

- [x] **Step 1: Define a job schema**

Require `schema_version`, `job_id`, `agent_pack`, `task`, `runtime`, `autonomy_tier`, `policy`, `workspace`, `eval_gate`, `receipt`, and `created_at`.

- [x] **Step 2: Add an example behavior-gate job**

Use `world-class-reviewer`, `codex-cli`, read-only autonomy, disposable workspace, all eval cases, and a local receipt target.

- [x] **Step 3: Document boundaries**

State that the job contract is not a scheduler, queue, or hosted service.

### Task 2: Codex Behavior Gate

**Files:**
- Create: `adapters/codex/run_behavior_gate.py`
- Modify: `adapters/codex/README.md`

- [x] **Step 1: Run static pack eval**

The gate shells to `run_pack_eval.py --json --no-write` and requires a pass.

- [x] **Step 2: Run Codex behavior eval**

The gate shells to `run_codex_behavior_eval.py --json`, forwarding selected cases and timeout.

- [x] **Step 3: Aggregate receipt**

The gate writes a `*.behavior-gate` receipt with job metadata, policy decision, static result, behavior result, checks, risks, and rollback.

### Task 3: Managed Platform Docs

**Files:**
- Modify: `README.md`
- Modify: `docs/MANAGED-AGENT-PLATFORM.md`
- Modify: `docs/EVAL-MATRIX.md`
- Modify: `docs/ADVERSARIAL_REVIEW.md`
- Modify: `docs/ROADMAP.md`

- [x] **Step 1: Promote behavior gate to V2 acceptance**

Make clear that a single bait case is not enough for platform confidence.

- [x] **Step 2: Add adversarial hard stops**

Document that a gate pass does not prove semantic excellence, web/mobile readiness, or provider agnosticism.

### Task 4: Verification

**Files:**
- No source changes.

- [x] **Step 1: Validate pack**

Run:

```powershell
python .\adapters\codex\validate_agent_pack.py .\agent-packs\world-class-reviewer --json
```

Result: `"ok": true` with 22/22 validator checks passing.

- [x] **Step 2: Compile Python scripts**

Run:

```powershell
python -m py_compile .\adapters\codex\validate_agent_pack.py .\adapters\codex\run_pack_eval.py .\adapters\codex\run_codex_behavior_eval.py .\adapters\codex\run_behavior_gate.py
```

Result: exit code 0.

- [x] **Step 3: Run full behavior gate**

Run:

```powershell
python .\adapters\codex\run_behavior_gate.py .\agent-packs\world-class-reviewer --json
```

Result: pass, 9/9 aggregate gate checks passed. Receipt written to `agent-packs/world-class-reviewer/receipts/runs/20260620T000635Z.behavior-gate/run-receipt.json`.
