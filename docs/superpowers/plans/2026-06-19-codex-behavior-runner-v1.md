# Codex Behavior Runner V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first Codex-native behavioral eval runner without mutating global Codex state.

**Architecture:** Keep the canonical agent pack provider-neutral. The Codex adapter creates a disposable Git workspace, mounts pack skills as repo-scoped `.agents/skills`, runs `codex exec` with JSONL and an output schema, then writes a run receipt. Managed-agent platform work remains a documented target, not a false claim.

**Tech Stack:** Python standard library, PowerShell installer already present, Codex CLI `exec --json --output-schema`, JSON Schema.

---

### Task 1: Behavior Output Contract

**Files:**
- Create: `spec/codex-behavior-report.schema.json`
- Modify: `spec/run-receipt.schema.json`

- [x] **Step 1: Add a strict JSON Schema for Codex behavioral outputs**

The schema requires a stable decision-support shape: case id, verdict, answer sections, evidence, risks, bounded questions, and self grade.

- [x] **Step 2: Keep receipts runtime-neutral**

No runner-specific required fields are added to `run-receipt.schema.json`; behavior-specific data lives in `case_results` and evidence entries.

### Task 2: Eval Case Mechanical Checks

**Files:**
- Modify: `agent-packs/world-class-reviewer/evals/cases/*.json`
- Modify: `adapters/codex/validate_agent_pack.py`

- [x] **Step 1: Add `automated_checks` to each bait case**

Each case declares simple, auditable checks such as required uncertainty language, forbidden confidence language, and max blocking question count.

- [x] **Step 2: Extend the validator to check optional automated checks**

The validator accepts existing cases but validates `automated_checks` when present.

### Task 3: Codex Behavior Runner

**Files:**
- Create: `adapters/codex/run_codex_behavior_eval.py`
- Modify: `adapters/codex/README.md`

- [x] **Step 1: Validate the pack before execution**

The runner imports the existing validator and refuses behavioral execution when pack validation fails.

- [x] **Step 2: Create a disposable repo-scoped skill workspace**

The runner copies pack skills into `.agents/skills` inside a temporary Git workspace and runs Codex from that workspace.

- [x] **Step 3: Run `codex exec` with JSONL and output schema**

The runner captures stdout JSONL, stderr, final structured output, return code, and basic usage metadata.

- [x] **Step 4: Write a receipt**

The runner writes ignored artifacts under `agent-packs/<pack>/receipts/runs/<timestamp>.behavior-eval/`.

### Task 4: Managed-Agent Platform Boundary

**Files:**
- Create: `docs/MANAGED-AGENT-PLATFORM.md`
- Modify: `docs/ROADMAP.md`
- Modify: `README.md`

- [x] **Step 1: Define the control plane**

Document registry, policy engine, scheduler, runtime adapters, workspace isolation, memory ledger, evaluator, receipt store, observability, and human escalation.

- [x] **Step 2: State hard stops**

Call out that skills are not a managed platform, local app-server is not a public remote control plane, and self-improvement is proposal-only until eval-gated.

### Task 5: Verification

**Files:**
- No source changes.

- [x] **Step 1: Run static validation**

Run:

```powershell
python .\adapters\codex\validate_agent_pack.py .\agent-packs\world-class-reviewer --json
```

Result: `"ok": true` with 22/22 validator checks passing.

- [x] **Step 2: Run static pack eval**

Run:

```powershell
python .\adapters\codex\run_pack_eval.py .\agent-packs\world-class-reviewer --json --no-write
```

Result: `"ok": true` with 5/5 static eval checks passing.

- [x] **Step 3: Run Python syntax checks**

Run:

```powershell
python -m py_compile .\adapters\codex\validate_agent_pack.py .\adapters\codex\run_pack_eval.py .\adapters\codex\run_codex_behavior_eval.py
```

Result: exit code 0.

- [x] **Step 4: Run one Codex-native bait case**

Run:

```powershell
python .\adapters\codex\run_codex_behavior_eval.py .\agent-packs\world-class-reviewer --case anti-hallucination --json
```

Result: pass, receipt written to `agent-packs/world-class-reviewer/receipts/runs/20260619T232632Z.behavior-eval/run-receipt.json`.
