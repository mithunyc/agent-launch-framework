# Read-Only Policy

Read-only mode is the default.

Allowed:

- inspect files
- inspect git state
- run non-mutating commands
- read official docs and primary sources
- produce findings, recommendations, and receipts

Blocked:

- editing files
- staging or committing
- pushing branches
- opening pull requests
- changing secrets
- changing infrastructure
- deploying
- writing to production systems

If a task requires mutation, stop and move to the write-safe policy.
