# Repository Wiring

## Current Safety Rule

Do not push from this folder until Git proves this local directory is wired to `https://github.com/mithunyc/agent-launch-framework`, not to the parent `titan-research` repository.

This folder may live physically inside `C:\Users\mshmi\OneDrive\Agents`, but it must have its own `.git` directory before staging or pushing.

## Verification Commands

Run from `C:\Users\mshmi\OneDrive\Agents\agent-launch-framework`:

```powershell
git status --short --untracked-files=all
git remote -v
gh repo view mithunyc/agent-launch-framework --json name,owner,url,isPrivate,defaultBranchRef
git ls-remote --symref https://github.com/mithunyc/agent-launch-framework.git HEAD
```

Interpretation:

- If `git remote -v` shows `mithunyc/titan-research`, this folder is still inside the parent repo context.
- If GitHub reports no default branch or `git ls-remote` prints no `HEAD`, the remote repository likely exists but has no initial commit yet.
- Do not use `git add .` from the parent `Agents` folder unless the intent is to commit the framework into `titan-research`.
- After the first push, verify that `git ls-remote --symref https://github.com/mithunyc/agent-launch-framework.git HEAD` points at `refs/heads/main`.

## Safe Publication Options

Preferred clean path:

1. Clone the empty GitHub repo to a separate temporary folder.
2. Copy only the `agent-launch-framework` contents into that checkout.
3. Run validation and gates again from the new checkout.
4. Commit and push from the checkout whose `origin` is `mithunyc/agent-launch-framework`.

Alternative path:

1. Initialize this folder as its own Git repo only after confirming it should no longer be tracked as part of the parent repository.
2. Set `origin` to `https://github.com/mithunyc/agent-launch-framework.git`.
3. Re-run validation and gates before the first push.

Rollback is deleting the temporary checkout or removing the accidental nested `.git` directory before any push.

## CI Publication Guard

The first push should include `.github/workflows/codex-gates.yml`. Static CI can pass without secrets. The full Codex proof requires an `OPENAI_API_KEY` repository secret and should fail if the secret is missing. Do not reinterpret that failure as a product bug; it is an unproven remote-runtime boundary.
