# Codex Plugin Packaging Gate V6

## Goal

Generate Codex plugin packaging from the proven `world-class-reviewer` pack inside `C:\Users\mshmi\OneDrive\Agents\agent-launch-framework` only, prove it through a disposable local marketplace and temporary `CODEX_HOME`, and avoid any claim about normal profile install, sharing, CI, cloud, mobile, or provider parity.

## Implementation

1. Added `adapters/codex/pack_fingerprint.py` so promotion receipts can bind to current canonical pack content.
2. Added `adapters/codex/package_plugin.py` to generate a Codex plugin, runtime-safe references, source metadata, and local marketplace metadata.
3. Added `adapters/codex/validate_plugin_package.py` to validate plugin manifests, marketplace source paths, policy fields, semver, skill frontmatter, and expected skill discovery without non-stdlib dependencies.
4. Added `adapters/codex/run_plugin_packaging_gate.py` to require a matching variance receipt, generate a disposable package under `.alf-runs/`, run negative plugin fixtures, install into a temporary `CODEX_HOME`, and verify `codex debug prompt-input` sees the plugin.
5. Updated docs and added a plugin-packaging managed job example.

## Adversarial Findings

- The plugin-creator validator could not run in the active Python environment because `yaml` was missing, so this framework needed its own stdlib validator.
- Generated packages under `agent-packs/.../receipts/runs/...` hit Windows path-length failures, so disposable plugin homes moved to ignored repo-local `.alf-runs/`.
- Hidden eval JSON should not be copied into runtime skill references; the generator now copies only DOD, policies, memory, and self-improvement policy.
- Python subprocess on Windows resolved bare `codex` to an access-denied target; the gate now resolves `codex.cmd`, `codex.exe`, then `codex`.

## Final Verification

- Pack validator: `ok=true`, 26/26 checks.
- Harness self-test: `ok=true`, 11/11 checks.
- Fingerprint-bound variance gate: `ok=true`, 31/31 checks, pack SHA `296d4ab62f149d6476ca2e6e24931121897b8e44cdd4a5096a811408b3cddf07`.
- Plugin packaging gate: `ok=true`, 49/49 checks.
- Packaging receipt: `agent-packs/world-class-reviewer/receipts/runs/20260620T062617Z.plugin-packaging-gate/run-receipt.json`.

## Residual Risk

- This proves disposable local Codex plugin packaging only.
- The normal user Codex profile was not mutated.
- The plugin was not published, shared, or installed into a real long-lived profile.
- CI, cloud, mobile, Claude, and local-LLM parity remain unproven.
- A second-opinion evaluator is still not built.

## Next Stress-Tested Step

Run plugin packaging variance three times and compare package fingerprints, marketplace metadata, CLI install outputs, and prompt-input discovery. Only after that stays stable, add the second-opinion evaluator.
