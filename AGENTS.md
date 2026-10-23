# Editing these notes

- Write the personal runbook in English. Keep README focused on installation,
  maintenance and recovery; keep old deployment details in `docs/migration.md`.
- Describe one concrete setup. Check commands against official sources and link
  them where used. Distinguish source review from actual installation, renewal,
  client-traffic and recovery tests. Never turn historical results into support
  claims for the new setup.
- Use upstream Marzban tooling. Do not add a custom installer, Compose stack,
  application wrapper or deployment framework.
- Repository work does not authorize VPS access, deployment, live subscription
  requests or bot actions. Server work needs an explicit request.
- Work in `dev`, fetch origin and integrate `origin/main` without rewriting
  history. Use Russian Conventional Commits and the owner's configured identity;
  do not override authorship or add co-author trailers. Push to `origin/dev` and
  open a PR to `main` after checks. Do not merge automatically.
- Before committing, stage intended files, run `python3 scripts/check.py` and
  `git diff --check`, and review the staged diff. No release checklist or ledger
  entry is required for an ordinary documentation edit.
- Preserve the annotated `legacy-ansible-2026-10-23` tag and historical evidence.
- Keep credentials, infrastructure addresses, user identifiers, live client links,
  databases and backups out of Git and tool output. Use obvious placeholders.
- Preserve unrelated local and ignored files. Never use broad cleanup commands.
  Necessary sensitive temporary files belong outside the checkout, mode 0600,
  and must be removed after use.
