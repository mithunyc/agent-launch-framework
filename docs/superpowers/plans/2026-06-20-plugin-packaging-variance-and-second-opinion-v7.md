# Plugin Packaging Variance And Second Opinion V7

## Goal

Stabilize the framework after disposable plugin packaging by adding deterministic package fingerprints, a repeated packaging variance gate, and an independent second-opinion evaluator before any CI, cloud, mobile, public plugin, or provider-parity claims.

## Changes

1. Added deterministic tree/package fingerprint helpers to the Codex adapter.
2. Removed volatile timestamps from generated plugin package metadata.
3. Added package and marketplace fingerprints to plugin package results and packaging-gate receipts.
4. Added `run_plugin_packaging_variance_gate.py` to repeat disposable plugin packaging three times and compare package fingerprints, marketplace fingerprints, CLI behavior, and prompt-input discovery digests.
5. Added `second_opinion_evaluator.py` to grade generic safety and usefulness invariants independently from case semantic rubrics.
6. Updated behavior, behavior gate, variance gate, harness self-test, job schema, and example jobs to require second-opinion checks.
7. Fixed runner receipts so saved JSON files include their own `written_to` path before being written.
8. Updated documentation to keep CI, cloud, mobile, public plugin, and provider parity claims blocked until separately proven.

## Receipts

- Behavior variance with second opinion: `agent-packs/world-class-reviewer/receipts/runs/20260620T071349Z.variance-gate/run-receipt.json`
- Plugin packaging variance: `agent-packs/world-class-reviewer/receipts/runs/20260620T071829Z.plugin-packaging-variance-gate/run-receipt.json`

## Verified Evidence

- Focused memory-hygiene variance passed after context-aware forbidden-phrase handling.
- Full variance passed: `36/36`, semantic scores `19/19` across three runs, second-opinion scores `40/40` across three runs.
- Plugin packaging variance passed: `13/13`.
- Final saved variance and packaging variance receipts include `written_to` in the JSON file, not only in stdout.
- Package fingerprint stayed stable: `0f5d5e695abec9e2c0d59ad48f6c41d57f836d1ac207e9f920a6f57306aa037a`.
- Marketplace fingerprint stayed stable: `b8e17f97046769b1518892c106f5d9268dcd2c785873685667163b70f2899871`.
- Prompt discovery digest stayed stable: `d369cb501850df39b7f5fd4f6aaa6339336b98fe5747476378206e32946085cb`.

## Risks

- The receipts prove this local Codex CLI and disposable plugin context only.
- Second-opinion is deterministic and useful, but it is not broad semantic intelligence.
- Self-grade drift remains telemetry; independent graders are the gate.
- CI, cloud, mobile/web, normal profile install, public plugin publishing, and provider parity remain unproven.
- The GitHub repo exists, but the local folder must be wired as its own repo before any push.

## Next Step

Create a clean checkout or initialize a dedicated repo for `mithunyc/agent-launch-framework`, then add a CI runner that executes validator, self-test, behavior gate, variance gate, and plugin packaging variance from a fresh environment.
