# Working on Mirage

## Purpose and boundaries

- Maintain English operating documentation for upstream Marzban. README and the
  four guides in `docs/` describe the current repository contract.
- Use official product documentation and source to verify commands and settings.
  Do not invent options or claim acceptance without an observed result.
- Keep the upstream-only setup distinct from the running legacy deployment.
  Record unresolved compatibility requirements in the migration guide.
- Do not introduce an installer, deployment framework, API wrapper, custom panel,
  subscription generator or backup service.
- Repository work must not connect to or modify a VPS, execute deployment
  commands, send bot messages or request live subscriptions. Server work requires
  an explicit user request covering those actions.

## Git and verification

- Work in `dev`. Fetch origin and integrate `origin/main` by fast-forward or a
  normal merge before a series of changes. Never force-push or rewrite history.
- Run `python3 scripts/check.py` and review `git diff --check` before committing.
  Stage new files first so the checker includes them.
- Use logical Conventional Commits in Russian and the owner's configured Git
  identity. Do not override author/committer or add co-author trailers.
- Push completed commits to `origin/dev`; open a PR to `main` once checks pass.
  Do not automatically merge it. Preserve the annotated legacy archive tag.
- Record factual acceptance evidence in `audit/acceptance-ledger.md`. Separate
  repository checks from installation, restoration and client-traffic tests.

## Secrets and local files

- Keep keys, passwords, tokens, infrastructure addresses, user UUIDs, live client
  links, databases and archives outside Git. Use obvious placeholders in examples.
- Inspect metadata instead of secret contents when it is sufficient. Never print
  secret values in logs, reports or failed checks.
- Any necessary sensitive temporary file must be outside the checkout, mode 0600,
  and removed after use.
- Preserve ignored and unrelated local files. Never use broad cleanup commands
  to remove old environments, generated documentation or private configuration.
