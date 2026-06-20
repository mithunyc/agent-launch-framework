# Agent Launch Framework

Unofficial framework for building portable, testable agent packs that can run through Codex first and other runtimes later.

This project is deliberately not named "Codex Managed Agents." Codex already provides skills, plugins, non-interactive execution, app automations, cloud tasks, MCP, and remote connections. A managed-agent platform requires an additional control plane with durable scheduling, state, memory, grading, and safety policy. This framework starts with the part that must be correct first: the agent pack contract.

## V0 Goal

Build a reusable public foundation for agent packs that are:

- installable into Codex as slash-command skills
- validated before installation
- graded against a definition of done
- supported by adversarial eval cases
- traceable through run receipts
- portable through adapter folders instead of provider-specific prompts

## V1 Goal

Prove the pack behaves inside Codex before adding cloud, mobile, or managed orchestration. V1 adds a Codex-native behavior runner that mounts skills only inside a disposable repo-scoped `.agents/skills` workspace, runs `codex exec` with JSONL, an output schema, clean-room flags, a temporary auth-only `CODEX_HOME`, hidden deterministic semantic rubrics, independent second-opinion checks, repeated-run variance checks, plugin packaging variance checks, and receipts.

## What This Is

- A canonical agent-pack layout.
- A Codex adapter with installer, uninstaller, validator, and local eval receipt tooling.
- A demo `world-class-reviewer` agent pack for evidence-first research, repo review, adversarial critique, and decision support.
- Documentation for runtime boundaries, evals, loops, memory, and safety policy.

## What This Is Not Yet

- Not an official OpenAI project.
- Not a managed cloud agent service.
- Not a guarantee of autonomous correctness.
- Not a self-modifying system.
- Not safe for unattended write/deploy actions without additional policy gates.

## Quickstart

From this folder:

```powershell
python .\adapters\codex\validate_agent_pack.py .\agent-packs\world-class-reviewer
python .\adapters\codex\run_harness_selftest.py .\agent-packs\world-class-reviewer
python .\adapters\codex\run_pack_eval.py .\agent-packs\world-class-reviewer
python .\adapters\codex\run_codex_behavior_eval.py .\agent-packs\world-class-reviewer --case anti-hallucination --clean-room
python .\adapters\codex\run_behavior_gate.py .\agent-packs\world-class-reviewer
python .\adapters\codex\run_variance_gate.py .\agent-packs\world-class-reviewer
python .\adapters\codex\run_plugin_packaging_gate.py .\agent-packs\world-class-reviewer
python .\adapters\codex\run_plugin_packaging_variance_gate.py .\agent-packs\world-class-reviewer
.\adapters\codex\install.ps1 -PackPath .\agent-packs\world-class-reviewer -DryRun
```

Fresh-checkout CI commands:

```powershell
python .\scripts\run_ci_gates.py --tier static --pack .\agent-packs\world-class-reviewer
python .\scripts\run_ci_gates.py --tier full --pack .\agent-packs\world-class-reviewer --timeout 600 --plugin-timeout 120
```

The static tier is dependency-free. The full tier requires a working Codex CLI and either `OPENAI_API_KEY` or `CODEX_HOME/auth.json`. In GitHub Actions, the full proof is manual and requires the repository secret `OPENAI_API_KEY`; see `docs/CI-REMOTE-PROOF.md`.

GitHub push and pull-request runs execute static gates only. To run the authenticated full Codex proof in GitHub, open Actions, choose `Codex Agent Gates`, run the workflow manually, and set `run_full_codex_proof=true`. That manual proof requires the repository secret `OPENAI_API_KEY`.

`run_behavior_gate.py` defaults to clean-room Codex execution by forwarding `--ignore-user-config`, `--ignore-rules`, and `--disable plugins` into `codex exec`, plus a temporary `CODEX_HOME` seeded only with `auth.json` when available. It also requires each case to pass hidden deterministic semantic rubrics stored in the eval case files but not sent in the prompt, plus an independent deterministic second-opinion evaluator for high-risk verdict alignment, evidence quality, uncertainty boundaries, risk inventory, rollback, and bounded human questions. Use `--use-user-config` only when diagnosing local plugin or personal-rule interactions; that mode is not promotion evidence.

`run_variance_gate.py` runs the full behavior gate three times by default, then requires stable gate scores, stable semantic scores, stable second-opinion scores, stable case statuses, stable safe verdict families, and bounded answer-fingerprint drift. Structural answer counts are bounded; the agent's own self-grade drift is recorded as telemetry but does not gate promotion because independent graders are the authority. This is the hard precondition before plugin packaging. It is still local Codex CLI evidence, not cloud/mobile/provider parity evidence.

`run_plugin_packaging_gate.py` requires a passing variance receipt bound to the current pack fingerprint, generates a Codex plugin and local marketplace under ignored `.alf-runs/`, validates the manifest and marketplace, proves bad plugin fixtures fail, installs the plugin into a temporary `CODEX_HOME`, and checks `codex debug prompt-input` for model-visible plugin discovery. This proves disposable local packaging only; it does not publish, share, or mutate the normal user Codex profile.

`run_plugin_packaging_variance_gate.py` repeats the disposable plugin packaging gate three times and compares package fingerprints, marketplace fingerprints, CLI install behavior, and prompt-input discovery digests. This is the promotion precondition before normal profile install, public/repo plugin packaging, CI, remote execution, mobile/web steering, or provider adapter parity.

If dry-run output is correct and the variance gate passes, install into Codex:

```powershell
.\adapters\codex\install.ps1 -PackPath .\agent-packs\world-class-reviewer
```

Then open a new Codex session and use:

```text
/world-class-reviewer
```

## Public Framework Shape

```text
agent-launch-framework/
  agent-packs/
    world-class-reviewer/
      agent.yaml
      dod.md
      skills/
      policies/
      evals/
      receipts/
      memory/
      self-improvement/
  adapters/
    codex/
      install.ps1
      uninstall.ps1
      validate_agent_pack.py
      run_pack_eval.py
      run_harness_selftest.py
      semantic_evaluator.py
      second_opinion_evaluator.py
      run_codex_behavior_eval.py
      run_behavior_gate.py
      run_variance_gate.py
      pack_fingerprint.py
      package_plugin.py
      validate_plugin_package.py
      run_plugin_packaging_gate.py
      run_plugin_packaging_variance_gate.py
  examples/
    jobs/
  scripts/
    run_ci_gates.py
  .github/
    workflows/
      codex-gates.yml
  docs/
  spec/
```

## Design Principles

1. Repo truth beats narrative.
2. Evals beat confidence.
3. Receipts beat chat memory.
4. Skills are behavior; plugins are distribution.
5. Memory is curated evidence, not a transcript dump.
6. Self-improvement is proposed by agents but accepted only by tests and human policy.
7. Autonomy is granted by risk tier, never by enthusiasm.
8. Semantic grading starts deterministic; model judges come only after rubric contracts are stable.
9. Repeated-run variance must be stable before packaging or remote claims.
10. Second-opinion checks gate promotion independently from the agent's own self-grade.
11. Plugin packaging must prove disposable local install and discovery before normal user profile install, sharing, CI, cloud, mobile, or provider parity claims.
12. Plugin packaging variance must be stable before CI, remote, mobile/web, or provider parity claims.
13. A green static CI job is not remote autonomy proof; the authenticated full Codex gate must pass in GitHub Actions first.

## Runtime Tiers

| Tier | Runtime | Status | Use |
|---|---|---:|---|
| T0 | Codex skill pack | V0 | Slash-command workflows and manual runs |
| T1 | Codex CLI runner | V1 | `codex exec`, clean-room flags, auth-only temporary `CODEX_HOME`, JSONL events, output schemas, receipts |
| T2 | Codex app automation | V1 | Scheduled local background tasks where host is online |
| T3 | Codex cloud or CI runner | V2 | Work that must run away from the user's PC; CI workflow exists, full remote proof requires configured auth and a green run |
| T4 | Portable provider adapters | V2+ | Claude, local models, custom hosted runtimes |

## Source Grounding

This framework is grounded in the current Codex model where skills are reusable workflows and plugins are the installable distribution unit:

- https://developers.openai.com/codex/skills
- https://developers.openai.com/codex/plugins
- https://developers.openai.com/codex/plugins/build
- https://developers.openai.com/codex/noninteractive
- https://developers.openai.com/codex/app/automations
- https://developers.openai.com/codex/app-server
- https://developers.openai.com/codex/subagents
- https://github.com/openai/codex

## Managed-Agent Platform Direction

See `docs/MANAGED-AGENT-PLATFORM.md`. The hard rule is that skills and plugins are not a managed-agent platform by themselves. Managed autonomy requires a control plane: job registry, policy engine, runtime adapters, isolated workspaces, receipts, evals, governed memory, and human escalation.

The current managed-platform seed is the job contract in `spec/managed-job.schema.json` plus the behavior, variance, and plugin-packaging example jobs in `examples/jobs/`.

## Repository Wiring

The intended public repository is `https://github.com/mithunyc/agent-launch-framework`. Do not assume the local folder is already a checkout of that repository. Verify `git remote -v`, `git status`, and the default branch before pushing or publishing; see `docs/REPOSITORY-WIRING.md`.

## CI And Remote Proof

The repository includes `.github/workflows/codex-gates.yml`. Static gates run on Ubuntu and Windows. The authenticated full Codex gate runs behavior, variance, and plugin packaging variance from a fresh checkout and should be treated as the first remote proof boundary.
