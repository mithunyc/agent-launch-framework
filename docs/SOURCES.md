# Source Grounding

This framework should track current runtime truth before making claims.

## Codex Sources

- Codex skills: https://developers.openai.com/codex/skills
- Codex plugins: https://developers.openai.com/codex/plugins
- Build Codex plugins: https://developers.openai.com/codex/plugins/build
- Codex non-interactive mode: https://developers.openai.com/codex/noninteractive
- Codex automations: https://developers.openai.com/codex/app/automations
- Codex command line reference: https://developers.openai.com/codex/cli/reference
- Codex app features: https://developers.openai.com/codex/app
- Codex cloud: https://developers.openai.com/codex/cloud
- Codex open source repo: https://github.com/openai/codex

## Local Runtime Observations

Observed on this workstation on 2026-06-19:

- `codex --version` returned `codex-cli 0.139.0`.
- `codex exec --help` exposed `--json`, `--output-schema`, `--sandbox`, `--profile`, `--cd`, `--ignore-user-config`, `--ignore-rules`, `--oss`, `--local-provider`, and `resume`.
- `codex exec --help` says `--ignore-user-config` does not load `$CODEX_HOME/config.toml` but auth still uses `CODEX_HOME`.
- `codex features list` reported `plugins` as a stable enabled feature on this workstation.
- The Codex environment reference says `CODEX_HOME` sets the root for config, auth, logs, sessions, skills, and package metadata.
- `codex plugin marketplace list` showed configured marketplaces.
- `codex doctor --json` reported local installation status `ok` and noted a newer CLI version was available.

These observations are runtime evidence, not permanent guarantees.

Observed on this workstation on 2026-06-20:

- `codex plugin marketplace add <local-root> --json` accepted a repo-local disposable marketplace root when `CODEX_HOME` pointed at `.alf-runs/.../codex-home`.
- `codex plugin list --marketplace alf-disposable --available --json` listed `world-class-reviewer@alf-disposable`.
- `codex plugin add world-class-reviewer@alf-disposable --json` installed into the temporary `CODEX_HOME` plugin cache, not the normal user profile.
- `codex debug prompt-input` showed the installed plugin as `World Class Reviewer` in the model-visible plugin list.
- Python subprocess on Windows needed the resolved `codex.cmd` path; bare `codex` produced `PermissionError: [WinError 5] Access is denied` in this environment.

These are local disposable proof points, not claims about public plugin sharing, normal profile install, CI, cloud, mobile, or provider parity.
