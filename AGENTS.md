# Agent Launch Framework Instructions

You are working on an unofficial public framework for portable agent packs. Optimize for evidence, safety, portability, and non-technical usability.

Do not claim this is an official OpenAI product. Do not claim it is a managed cloud agent platform until a durable hosted runner exists.

Before changing behavior:

1. Inspect the current pack layout and adapter code.
2. Preserve the canonical pack contract unless the schema, docs, validator, and demo pack are updated together.
3. Keep Codex-specific logic under `adapters/codex/`.
4. Keep provider-neutral behavior inside `agent-packs/`, `spec/`, and `docs/`.
5. Add or update eval cases for every new capability.
6. Run the validator and local eval runner before claiming done.

Safety rules:

- Default to read-only and advisory behavior.
- Treat write, deploy, secret, money, legal, regulatory, safety, and data-loss tasks as high risk.
- Agent memory must include source, confidence, expiry, and reason.
- Self-improvement proposals must not directly mutate installed skills without validation and human approval.

Done means:

- Files changed are listed.
- Validator output is shown.
- Eval output is shown.
- Remaining risks are stated.
- Rollback is clear.
