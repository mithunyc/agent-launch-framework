# Codex Adapter

This adapter installs and validates agent packs for Codex.

## Commands

Validate a pack:

```powershell
python .\adapters\codex\validate_agent_pack.py .\agent-packs\world-class-reviewer
```

Run static eval checks and write a receipt:

```powershell
python .\adapters\codex\run_pack_eval.py .\agent-packs\world-class-reviewer
```

Run deterministic harness self-tests against positive and broken pack/output fixtures:

```powershell
python .\adapters\codex\run_harness_selftest.py .\agent-packs\world-class-reviewer --json
```

Run a Codex-native behavioral baitset without global install:

```powershell
python .\adapters\codex\run_codex_behavior_eval.py .\agent-packs\world-class-reviewer --case anti-hallucination --clean-room --json
```

Behavior artifacts are written under `agent-packs\<pack>\receipts\runs\*.behavior-eval\` unless `--no-write` is used. These artifacts are ignored by git.

Use `--shared-codex-home` with the raw behavior runner only when diagnosing normal local Codex state. Promotion evidence should leave this unset.

Run the managed behavior gate:

```powershell
python .\adapters\codex\run_behavior_gate.py .\agent-packs\world-class-reviewer --json
```

The gate runs static pack evals, all Codex behavior cases by default, hidden semantic rubric checks, independent second-opinion checks, policy checks, and writes a `*.behavior-gate` receipt. It defaults to clean-room Codex execution by forwarding `--ignore-user-config`, `--ignore-rules`, and `--disable plugins` into `codex exec`, then setting a temporary `CODEX_HOME` seeded only with `auth.json` when available.

Semantic rubrics live in `agent-packs\<pack>\evals\cases\*.json` under `semantic_rubric`. They are not included in the prompt given to Codex; `semantic_evaluator.py` grades the final structured JSON afterward. This is intentionally deterministic and dependency-free. It catches false-positive answers before a future model-judge or cloud runner exists.

`second_opinion_evaluator.py` is also deterministic and dependency-free. It grades generic safety and usefulness invariants that should hold across cases: required output shape, high-risk verdict alignment, forbidden overclaim boundaries, evidence quality, uncertainty boundary, risk inventory, rollback, bounded blocking questions, sane self-grade shape, and usable recommendation.

Run the repeated-run variance gate:

```powershell
python .\adapters\codex\run_variance_gate.py .\agent-packs\world-class-reviewer --json
```

The variance gate runs the full behavior gate three times by default and compares gate scores, semantic scores, second-opinion scores, case statuses, safe verdict families, structural counts, and answer-fingerprint drift. It writes a `*.variance-gate` receipt. By default, child behavior gates run with `--no-write` so the variance receipt is the durable artifact; use `--keep-child-receipts` only when you need deep per-run artifacts.

Passing variance is the hard precondition before generating Codex plugin packaging. It still proves only local repeated Codex CLI behavior, not CI, cloud, mobile, or provider-adapter parity.

Generate and validate Codex plugin packaging in a disposable local marketplace:

```powershell
python .\adapters\codex\run_plugin_packaging_gate.py .\agent-packs\world-class-reviewer --json
```

The packaging gate requires a passing variance receipt whose pack fingerprint matches the current canonical pack. It writes the receipt under `agent-packs\<pack>\receipts\runs\*.plugin-packaging-gate\`, generates the disposable plugin home under ignored `.alf-runs\`, validates `.codex-plugin\plugin.json` and `.agents\plugins\marketplace.json`, runs negative plugin fixture checks, installs the plugin into a temporary `CODEX_HOME`, and verifies `codex debug prompt-input` can see the plugin. It does not mutate the normal user Codex profile.

Run packaging variance before normal profile install, sharing, CI, remote, mobile/web, or provider parity claims:

```powershell
python .\adapters\codex\run_plugin_packaging_variance_gate.py .\agent-packs\world-class-reviewer --json
```

The packaging variance gate repeats disposable packaging three times and compares package fingerprints, marketplace fingerprints, CLI install behavior, and prompt-input discovery digests.

Generate a plugin package manually when you only need the disposable artifact:

```powershell
python .\adapters\codex\package_plugin.py .\agent-packs\world-class-reviewer --output-root .\.alf-runs\manual-package\plugin-home --force --json
python .\adapters\codex\validate_plugin_package.py .\.alf-runs\manual-package\plugin-home --expected-plugin world-class-reviewer --expected-skill world-class-reviewer --json
```

Use local user config only for diagnostics:

```powershell
python .\adapters\codex\run_behavior_gate.py .\agent-packs\world-class-reviewer --use-user-config --json
```

That mode is intentionally not promotion evidence because local plugins or personal instructions can contaminate results.

Dry-run install:

```powershell
.\adapters\codex\install.ps1 -PackPath .\agent-packs\world-class-reviewer -DryRun
```

Install:

```powershell
.\adapters\codex\install.ps1 -PackPath .\agent-packs\world-class-reviewer
```

Uninstall:

```powershell
.\adapters\codex\uninstall.ps1 -PackId world-class-reviewer
```

## Install Behavior

The installer mounts each pack skill into:

```text
%CODEX_HOME%\skills
```

or, when `CODEX_HOME` is unset:

```text
%USERPROFILE%\.codex\skills
```

By default it uses junctions on Windows and symbolic links elsewhere. Use `-Mode Copy` when links are not allowed.

## Safety

- Validation runs before install unless `-SkipValidation` is provided.
- Existing skill folders are not overwritten unless `-Force` is provided.
- `-Force` removes only targets inside the selected Codex skill root.
- Uninstall removes only entries recorded in the adapter manifest.
- Behavior evals copy skills into a disposable repo-scoped `.agents\skills` workspace and do not mutate global Codex skill folders.
- Clean-room behavior evals use a temporary auth-only `CODEX_HOME` and disable plugins; the temporary Codex home is deleted even when `--keep-workspace` is used.
- Harness self-tests copy broken fixtures into temporary directories, require them to fail validation, and verify known-good/known-bad semantic and variance outputs.
- Plugin packaging uses ignored repo-local `.alf-runs\` scratch space and a temporary `CODEX_HOME`; it must not write to the normal user plugin home during promotion tests.
- Plugin packaging variance must remain stable before using a normal profile, publishing, CI, remote execution, mobile/web steering, or provider parity.
