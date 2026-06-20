# Architecture

## Problem

Most agent folders mix prompts, runtime assumptions, tools, memory, and safety policy into one blob. That makes them hard to validate, hard to install, and easy to overclaim.

This framework separates the concerns:

- **Agent pack:** provider-neutral mission, behavior, policies, evals, receipts, and memory rules.
- **Adapter:** runtime-specific installation and execution wiring.
- **Runner:** optional execution loop that invokes a runtime, records receipts, and applies grading.
- **Control plane:** future hosted layer for scheduling, dashboards, durable state, and remote operation.

## V0 Boundary

V0 ships an agent-pack contract and a Codex adapter. It does not ship a managed cloud runtime.

This is the right first boundary because the pack format must be stable before any runner can safely automate it.

## Canonical Pack Layout

```text
agent-pack/
  agent.yaml
  dod.md
  skills/
    <skill-name>/SKILL.md
  policies/
    read-only.md
    write-safe.md
    secret-safe.md
  evals/
    cases/*.json      # prompts, expected behavior, mechanical checks, hidden semantic rubrics
  receipts/
    template.run-receipt.json
  memory/
    README.md
  self-improvement/
    README.md
```

## Runtime Adapter Contract

Every adapter must provide:

- install or mount instructions
- validation before install
- uninstall or rollback path
- runtime limitations
- eval command
- receipt command or receipt format

## Codex Adapter

The Codex adapter installs pack skills into `CODEX_HOME/skills` or `~/.codex/skills`.

It uses junctions or symbolic links by default so the source pack remains version-controlled and easy to update. Copy mode is available for distribution or locked-down environments.

## Future Runner Loop

The runner should eventually follow this loop:

1. Load `agent.yaml`.
2. Select runtime adapter.
3. Build a bounded prompt from the user task, `dod.md`, policy, and eval context.
4. Execute through `codex exec` or another runtime.
5. Capture JSONL events and final output.
6. Score against mechanical checks, hidden semantic rubrics, deterministic second-opinion checks, and the definition of done.
7. Compare repeated-run variance before packaging or promotion.
8. For plugin distribution, require a current pack fingerprint-bound variance receipt, disposable marketplace validation, temp-`CODEX_HOME` install, and prompt-input discovery.
9. Repeat plugin packaging and compare package fingerprints, marketplace fingerprints, CLI behavior, and prompt-input discovery before publishing or remote claims.
10. Write a receipt.
11. Propose memory or skill updates.
12. Apply updates only after validation and human approval.
