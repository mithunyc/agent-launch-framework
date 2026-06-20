# Clean-Room And Negative Fixtures V3

**Goal:** Harden the Agent Launch Framework behavior gate before plugin, cloud, mobile, or managed-agent work.

**Architecture:** Keep the canonical agent pack provider-neutral. The Codex adapter remains local and read-only, but promotion evidence now runs `codex exec` in clean-room mode and the harness proves known-bad fixtures fail before behavior receipts are trusted.

## Scope

- Modify: `adapters/codex/run_codex_behavior_eval.py`
- Modify: `adapters/codex/run_behavior_gate.py`
- Create: `adapters/codex/run_harness_selftest.py`
- Modify: `spec/managed-job.schema.json`
- Modify: `examples/jobs/world-class-reviewer-behavior-gate.job.json`
- Modify: docs and quickstart references

## Plan

- [x] **Step 1: Add clean-room Codex execution controls**

`run_codex_behavior_eval.py` supports `--clean-room`, which forwards `--ignore-user-config`, `--ignore-rules`, and `--disable plugins` into `codex exec` and uses a temporary auth-only `CODEX_HOME` by default. `run_behavior_gate.py` defaults to clean-room and exposes `--use-user-config` only for diagnostics.

- [x] **Step 2: Make clean-room visible in receipts and job contracts**

Gate jobs include `runtime.clean_room`, `runtime.isolated_codex_home`, and `runtime.codex_exec_flags`. Receipts include clean-room, isolated-home checks, evidence, and risk text.

- [x] **Step 3: Add deterministic negative fixture self-tests**

`run_harness_selftest.py` validates the real pack as a positive control, then copies and breaks fixtures for skill frontmatter, eval cases, unsafe claims, and job required fields. The harness passes only when those broken fixtures fail.

- [x] **Step 4: Update operator docs**

Docs now put harness self-tests before live Codex behavior runs, separate diagnostic user-config mode from promotion evidence, and record the V1.6 hardening step.

- [x] **Step 5: Verify**

Run Python compile checks, pack validation, JSON parsing, harness self-tests, a clean-room single-case gate, and a full clean-room behavior gate.

Evidence from 2026-06-20 UTC:

- `python -m py_compile ...` passed.
- JSON parse of all framework `*.json` files returned `JSON_OK`.
- `validate_agent_pack.py --json` returned `ok: true` with 22/22 validator checks.
- `run_harness_selftest.py --json` returned `ok: true`, 6/6 checks, receipt `agent-packs/world-class-reviewer/receipts/runs/20260620T004439Z.harness-selftest/run-receipt.json`.
- Single-case clean-room smoke gate returned `ok: true`, 8/8 aggregate checks, 12/12 behavior checks.
- Full clean-room behavior gate returned `ok: true`, 11/11 aggregate checks, 36/36 behavior checks, receipt `agent-packs/world-class-reviewer/receipts/runs/20260620T004514Z.behavior-gate/run-receipt.json`.
- Child behavior eval receipt: `agent-packs/world-class-reviewer/receipts/runs/20260620T004514Z.behavior-eval/run-receipt.json`.
- Post-run `validate_agent_pack.py --json` still returned `ok: true`.
- No `%TEMP%\alf-*` directories remained after the full run.

## Hard Stops

- Do not mutate global Codex skill folders.
- Do not touch Titan files or UnionForge files.
- Do not call local user-config runs promotion evidence.
- Do not treat mechanical gate success as semantic excellence or managed-platform readiness.

## Rollback

Delete the V3-added files and revert edits in the Codex adapter, schema, example job, and docs. Generated receipts can be removed from `agent-packs/world-class-reviewer/receipts/runs/`.
