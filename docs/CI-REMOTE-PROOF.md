# CI And Remote Proof

This repository uses two gate tiers.

## Static Gates

The static gate runs on Ubuntu and Windows without secrets:

```powershell
python scripts/run_ci_gates.py --tier static --pack agent-packs/world-class-reviewer
```

It checks:

- Python syntax for Codex adapter scripts.
- JSON syntax outside generated run artifacts.
- Agent pack validation.
- Static pack eval.
- Harness self-test.

## Full Codex Gates

The full gate runs the static tier plus:

- Codex behavior gate.
- Three-run behavior variance gate.
- Three-run plugin packaging variance gate.

Local command:

```powershell
python scripts/run_ci_gates.py --tier full --pack agent-packs/world-class-reviewer --timeout 600 --plugin-timeout 120
```

Remote GitHub Actions command:

```bash
npm install -g "@openai/codex@${CODEX_CLI_VERSION}"
python scripts/run_ci_gates.py --tier full --pack agent-packs/world-class-reviewer --timeout 600 --plugin-timeout 120
```

The GitHub workflow intentionally fails the full proof when `OPENAI_API_KEY` is not configured. A green static job without a green full proof is not enough to claim managed-agent autonomy, mobile/web availability, or provider parity.

## Required GitHub Secret

Configure this repository secret before treating CI as remote proof:

- `OPENAI_API_KEY`

The workflow pins `@openai/codex` through `CODEX_CLI_VERSION` in `.github/workflows/codex-gates.yml`. Update that pin intentionally and re-run the full gate when Codex CLI behavior changes.

## Promotion Rule

Do not add public marketplace packaging, mobile/web runtime claims, or Claude/provider parity claims until the full Codex gate is green in GitHub Actions from a fresh checkout.

Rollback for CI changes is deleting `.github/workflows/codex-gates.yml`, `scripts/run_ci_gates.py`, and this document.
