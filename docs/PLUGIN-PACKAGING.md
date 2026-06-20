# Codex Plugin Packaging

Codex plugins are the correct public distribution target once the agent pack format is proven.

## Current Decision

The first packaging gate and packaging variance gate now exist, but only for disposable local proof.

It does not install into the normal user Codex profile, publish a public plugin, share a workspace plugin, or prove CI/cloud/mobile/provider parity. That restraint is intentional: plugin distribution should only follow pack validation, behavioral gates, repeated-run behavior variance, and repeated-run packaging variance.

## Local Evidence

Local installed plugins use:

```text
<plugin>/
  .codex-plugin/plugin.json
  skills/
  assets/
  .mcp.json
  .app.json
```

Local marketplaces use:

```text
.agents/plugins/marketplace.json
```

The observed `plugin.json` shape includes:

- `name`
- `version`
- `description`
- `author`
- `homepage`
- `repository`
- `license`
- `keywords`
- `skills`
- optional `mcpServers`
- optional `apps`
- `interface`

## Disposable Packaging Gate

Run:

```powershell
python .\adapters\codex\run_plugin_packaging_gate.py .\agent-packs\world-class-reviewer --json
```

The gate:

1. Requires a passing variance receipt whose pack fingerprint matches the current pack.
2. Generates a plugin under ignored `.alf-runs/<run>/plugin-home/plugins/<pack-id>`.
3. Generates `.alf-runs/<run>/plugin-home/.agents/plugins/marketplace.json`.
4. Validates plugin manifest, marketplace metadata, source path safety, policy fields, semver, and skill frontmatter.
5. Runs negative fixtures for missing plugin manifest, unsafe marketplace path, and broken skill frontmatter.
6. Adds the local marketplace inside a temporary `CODEX_HOME`.
7. Installs the plugin inside that temporary `CODEX_HOME`.
8. Uses `codex debug prompt-input` to prove model-visible plugin discovery.

The generated plugin copies runtime-safe pack references into the packaged skill: DOD, policies, memory policy, and self-improvement policy. Eval cases and hidden semantic rubrics are intentionally not copied into runtime skill references.

Do not use a normal user plugin home as first proof. The first packaging proof should use a disposable plugin home or local marketplace fixture so a bad package cannot contaminate global Codex plugin discovery.

## Packaging Variance Gate

Run:

```powershell
python .\adapters\codex\run_plugin_packaging_variance_gate.py .\agent-packs\world-class-reviewer --json
```

The variance gate repeats the disposable packaging gate three times and requires:

1. All child packaging gates pass.
2. Package fingerprints remain identical.
3. Marketplace fingerprints remain identical.
4. CLI install/list behavior remains stable after normalizing per-run scratch paths.
5. `codex debug prompt-input` discovery digests remain identical.
6. The expected plugin skill remains visible only inside the disposable/local marketplace context.

This is still local proof. It does not prove public marketplace publishing, normal user profile install, cloud, mobile, or provider parity. CI only becomes remote packaging proof after the authenticated full Codex GitHub Actions job passes from a fresh checkout.

## Manual Artifact Commands

Generate and validate a disposable package without running the CLI install smoke:

```powershell
python .\adapters\codex\package_plugin.py .\agent-packs\world-class-reviewer --output-root .\.alf-runs\manual-package\plugin-home --force --json
python .\adapters\codex\validate_plugin_package.py .\.alf-runs\manual-package\plugin-home --expected-plugin world-class-reviewer --expected-skill world-class-reviewer --json
```

Rollback is deletion of the generated `.alf-runs/<run>` directory and the matching `*.plugin-packaging-gate` or `*.plugin-packaging-variance-gate` receipt directory.

For CI usage, prefer:

```powershell
python .\scripts\run_ci_gates.py --tier full --pack .\agent-packs\world-class-reviewer --timeout 600 --plugin-timeout 120
```
