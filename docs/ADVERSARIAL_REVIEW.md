# Adversarial Review

## Contrarian Findings

1. A prompt folder is not an agent platform.
2. A global skill install can poison every repo if validation is weak.
3. "Self-learning" can silently preserve hallucinations unless memory is curated and reversible.
4. Evals can reward style instead of truth unless they include failure modes and evidence requirements.
5. Cloud autonomy and mobile access are runtime problems, not prompt problems.
6. Non-technical usability fails if setup requires reading ten docs before the first useful run.

## Stress Questions

| Question | Decision |
|---|---|
| Should V0 build cloud autonomy? | No. Build pack contract and Codex adapter first. |
| Should agents edit their own skills automatically? | No. They may propose changes, but validation and approval gate them. |
| Should write/deploy actions be allowed by default? | No. Default read-only and advisory. |
| Should memory store raw chat? | No. Store curated lessons with evidence and expiry. |
| Should the pack claim provider agnosticism immediately? | No. It can be adapter-ready, then prove each runtime. |
| Should plugin packaging be included before validation works? | No. Plugin packaging follows a proven pack. |
| Does one passing behavior case prove platform readiness? | No. Run the managed behavior gate across every bait case. |
| Does a job contract mean this is a hosted managed-agent service? | No. It is only an auditable envelope for a future control plane. |
| Can a gate be trusted if it never sees bad fixtures? | No. Run harness self-tests that prove known-bad packs and jobs fail. |
| Can local user config be used as promotion evidence? | No. It is diagnostic only; promotion gates should use clean-room Codex execution with temporary auth-only `CODEX_HOME`. |
| Does a deterministic semantic rubric prove expert judgment? | No. It catches known semantic failure modes; it does not prove broad reasoning quality. |
| Does a second-opinion evaluator prove broad correctness? | No. It catches generic safety and usefulness failures that a case rubric might miss. |
| Does one full behavior-gate pass prove stable behavior? | No. Run repeated clean-room gates and compare semantic scores, statuses, safe verdict families, and answer-fingerprint drift. |
| Does a generated plugin folder prove Codex install readiness? | No. Validate the marketplace, run negative plugin fixtures, install inside a temporary `CODEX_HOME`, and inspect prompt-input discovery. |
| Does disposable plugin install prove public sharing, mobile, cloud, or provider parity? | No. It proves only local disposable Codex plugin packaging. |
| Does one disposable plugin packaging pass prove distribution stability? | No. Repeat packaging and compare package fingerprints, marketplace fingerprints, CLI behavior, and prompt-input discovery. |
| Should the agent's self-grade block promotion? | No. Record it as telemetry; independent semantic and second-opinion graders gate promotion. |

## V0 Hard Stops

- Missing validator.
- Missing eval cases.
- Missing rollback.
- Claims of official OpenAI status.
- Claims of guaranteed correctness.
- Secrets in agent pack files.
- Runtime-specific assumptions in provider-neutral docs.
- Treating one passing bait case as proof of platform readiness.
- Treating a job contract as a scheduler, queue, or hosted managed-agent service.
- Treating deterministic semantic rubric success as proof of broad expert judgment.
- Treating second-opinion success as proof of broad correctness.
- Treating a passing harness as meaningful before negative fixtures prove failure paths.
- Treating local user config, plugin cache, global skills, or personal rules as neutral runtime conditions.
- Treating one lucky clean-room run as packaging evidence.
- Treating local variance stability as proof of CI, cloud, mobile, or provider parity.
- Treating plugin packaging as proof of normal profile install, workspace sharing, CI, cloud, mobile, or Claude/local-model parity.
- Treating plugin packaging variance as proof of CI or public marketplace behavior before CI actually runs it.

## Current Stress-Test Rule

Before normal profile install, cloud/mobile work, or provider adapters, run harness self-tests, the repeated-run variance gate across every bait case, the disposable plugin packaging gate, and the plugin packaging variance gate. A pass means the selected negative fixtures, current baitset, deterministic semantic rubrics, second-opinion checks, mechanical checks, local repeated-run variance thresholds, local plugin packaging, temp-`CODEX_HOME` install, package fingerprints, marketplace fingerprints, and prompt-input discovery passed. It does not mean the agent is broadly correct, vendor agnostic, safe for unattended writes, published, shared, or proven outside the local Codex CLI/app surfaces.
