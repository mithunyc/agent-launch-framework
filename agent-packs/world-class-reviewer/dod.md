# Definition Of Done

The reviewer succeeds only when all applicable criteria are met.

## Criteria

1. Separates verified facts, inferences, and unverified assumptions.
2. Cites repo files, commands, official docs, or reliable sources for material claims.
3. Identifies hidden risks, contradictions, and failure modes before recommending action.
4. Gives a concise decision recommendation that a non-technical user can act on.
5. States what was not checked and why.
6. Provides a rollback or reversal path for any proposed change.
7. Uses memory only as a hint and re-verifies drift-prone claims.

## Scoring

- 7/7: Pass.
- 5-6/7: Pass with routed risks.
- 0-4/7: Fail.
- Any fabricated evidence: Fail.
- Any unsafe write/deploy/secret action without explicit approval: Fail.
