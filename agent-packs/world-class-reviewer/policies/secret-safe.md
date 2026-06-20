# Secret-Safe Policy

Never ask the user to paste secrets into chat.

Allowed:

- tell the user where a secret should be stored
- check whether an environment variable is set without printing its value
- verify that secret files are ignored
- recommend rotation if a secret was exposed

Blocked:

- printing secrets
- committing secrets
- copying secrets into prompts
- storing secrets in memory
- writing secrets into receipts

Secret receipts should record only:

- variable name
- storage location class
- verification method
- whether it was present
