# Agent Launch Framework V0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a public, unofficial v0 foundation for portable agent packs with a Codex adapter, validator, eval runner, receipt template, and demo expert-reviewer pack.

**Architecture:** Keep provider-neutral contract files under `agent-packs/`, `spec/`, and `docs/`. Keep Codex-specific install and validation code under `adapters/codex/`. Prove the pack contract before adding cloud or managed-agent claims.

**Tech Stack:** Markdown, JSON Schema, Python standard library, PowerShell, Codex skills.

---

### Task 1: Provider-Neutral Documentation

**Files:**
- Create: `README.md`
- Create: `AGENTS.md`
- Create: `docs/ARCHITECTURE.md`
- Create: `docs/EVAL-MATRIX.md`
- Create: `docs/ADVERSARIAL_REVIEW.md`
- Create: `docs/LOOPS.md`
- Create: `docs/ROADMAP.md`

- [x] **Step 1: Define the public boundary**

State that the project is unofficial, starts with agent packs, and does not yet claim managed cloud autonomy.

- [x] **Step 2: Define the runtime tiers**

Document Codex skills, Codex CLI, Codex app automations, Codex cloud/CI, and portable provider adapters as separate tiers.

- [x] **Step 3: Define adversarial failure modes**

Document fake autonomy, global-install poisoning, unsafe self-learning, weak evals, and memory drift.

### Task 2: Canonical Pack Spec

**Files:**
- Create: `spec/agent-pack.schema.json`
- Create: `spec/run-receipt.schema.json`

- [x] **Step 1: Define required pack fields**

Require identity, version, mission, runtimes, skills, policies, evals, receipts, memory, and self-improvement.

- [x] **Step 2: Define run receipt fields**

Require task, runtime, evidence, checks, score, risks, memory proposals, and rollback.

### Task 3: Demo Agent Pack

**Files:**
- Create: `agent-packs/world-class-reviewer/agent.yaml`
- Create: `agent-packs/world-class-reviewer/dod.md`
- Create: `agent-packs/world-class-reviewer/skills/world-class-reviewer/SKILL.md`
- Create: `agent-packs/world-class-reviewer/policies/read-only.md`
- Create: `agent-packs/world-class-reviewer/policies/write-safe.md`
- Create: `agent-packs/world-class-reviewer/policies/secret-safe.md`
- Create: `agent-packs/world-class-reviewer/evals/cases/*.json`
- Create: `agent-packs/world-class-reviewer/receipts/template.run-receipt.json`
- Create: `agent-packs/world-class-reviewer/memory/README.md`
- Create: `agent-packs/world-class-reviewer/self-improvement/README.md`

- [x] **Step 1: Create an evidence-first reviewer agent**

The first pack performs research, repo review, forensic audit, adversarial critique, and decision support.

- [x] **Step 2: Add policy gates**

Default behavior is read-only and advisory. Write/deploy/secret actions are not allowed without explicit policy.

- [x] **Step 3: Add adversarial eval cases**

Cases test anti-hallucination, unsafe autonomy, memory hygiene, and non-technical usability.

### Task 4: Codex Adapter

**Files:**
- Create: `adapters/codex/README.md`
- Create: `adapters/codex/validate_agent_pack.py`
- Create: `adapters/codex/run_pack_eval.py`
- Create: `adapters/codex/install.ps1`
- Create: `adapters/codex/uninstall.ps1`

- [x] **Step 1: Validate before install**

Validator checks frontmatter, required files, policies, evals, receipts, memory rules, and unsafe claims.

- [x] **Step 2: Install safely**

Installer supports dry-run, junction/symlink install, copy mode, force only under the skill root, and manifest recording.

- [x] **Step 3: Uninstall safely**

Uninstaller reads the manifest and removes only framework-installed skill targets.

### Task 5: Verification

**Files:**
- Use: `adapters/codex/validate_agent_pack.py`
- Use: `adapters/codex/run_pack_eval.py`
- Use: `adapters/codex/install.ps1`

- [x] **Step 1: Run validator**

Run: `python .\adapters\codex\validate_agent_pack.py .\agent-packs\world-class-reviewer --json`

Observed: PASS, 18/18 checks passed.

- [x] **Step 2: Run local eval runner**

Run: `python .\adapters\codex\run_pack_eval.py .\agent-packs\world-class-reviewer --json`

Observed: PASS, 5/5 static eval checks passed.

- [x] **Step 3: Run install dry-run**

Run: `.\adapters\codex\install.ps1 -PackPath .\agent-packs\world-class-reviewer -DryRun`

Observed: PASS, dry-run target was `C:\Users\mshmi\.codex\skills\world-class-reviewer`.
