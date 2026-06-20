# Repo CI Remote Proof V8

## Assumptions

- `C:\Users\mshmi\OneDrive\Agents\agent-launch-framework` is the intended local source for `mithunyc/agent-launch-framework`.
- The GitHub remote exists but may not have an initial commit yet.
- Remote proof means a fresh GitHub runner can execute the same promotion gates, not merely that files were pushed.

## Decision

Create a dedicated Git repo inside `agent-launch-framework`, add CI that separates dependency-free static gates from authenticated Codex gates, and make missing Codex auth a hard stop.

## Adversarial Checks

- If Git still points at `mithunyc/titan-research`, stop before staging.
- If full CI has no `OPENAI_API_KEY`, fail instead of silently skipping behavior evidence.
- If packaging variance is run with `--no-write`, child packaging gates must also avoid writing receipts.
- A green static job is not enough for managed-agent, mobile/web, or provider-parity claims.

## Verification Commands

```powershell
git rev-parse --show-toplevel
git remote -v
python scripts/run_ci_gates.py --tier static --pack agent-packs/world-class-reviewer
python scripts/run_ci_gates.py --tier full --pack agent-packs/world-class-reviewer --timeout 600 --plugin-timeout 120
```

## Rollback

- Remove `.git` only if no push has happened and this folder should return to being parent-repo untracked content.
- Delete `.github/workflows/codex-gates.yml`, `scripts/run_ci_gates.py`, `docs/CI-REMOTE-PROOF.md`, this plan, and revert the packaging variance `--no-write` propagation.
