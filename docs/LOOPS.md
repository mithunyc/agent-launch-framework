# Loops

The framework uses loops as an operating model, but every loop must be bounded by policy and evidence.

## Core Loop

```text
intake -> plan -> execute -> verify -> grade semantics -> receipt -> learn -> propose improvement
```

## Read-Only Advisory Loop

Use this for research, review, forensic audit, strategic critique, and decision support.

1. Restate the task and assumptions.
2. Gather evidence from source files, commands, official docs, or cited sources.
3. Identify risks, contradictions, and missing proof.
4. Score against `dod.md` and hidden semantic rubrics when eval cases exist.
5. Write a receipt.
6. Ask only minimum blocking questions.

## Write-Safe Loop

Use this only when the pack policy permits edits.

1. Create or verify isolated branch/worktree.
2. Define rollback.
3. Make the smallest scoped change.
4. Run checks.
5. Produce a receipt.
6. Stop before merge/deploy unless the policy explicitly allows it.

## Self-Improvement Loop

Self-improvement is proposal-driven, not self-mutating.

1. Agent identifies a failure or repeated weakness.
2. Agent writes an improvement proposal with evidence.
3. Eval cases are added or updated first.
4. Proposed skill/policy changes are applied in a branch.
5. Validator and evals must pass.
6. Human or configured policy approves promotion.
