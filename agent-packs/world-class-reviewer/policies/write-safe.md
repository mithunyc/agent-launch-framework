# Write-Safe Policy

Write-safe mode requires explicit user authorization.

Before writing:

1. Confirm the target folder.
2. Check git branch and status.
3. Identify unrelated existing changes.
4. Define rollback.
5. Keep edits scoped to the requested task.

Blocked unless separately approved:

- production deploys
- database migrations
- destructive filesystem operations
- secret changes
- billing changes
- permission or auth changes

After writing:

1. Run relevant checks.
2. Show evidence.
3. State residual risks.
4. State rollback.
