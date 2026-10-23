# Contributing

Mirage contains English operating documentation for upstream Marzban and a small
offline repository checker. Keep changes focused on an actual operating need.
Application features and protocol implementations belong upstream.

## Workflow

Work in `dev`, integrating `origin/main` without rewriting history. Use the
owner's configured Git identity and Russian Conventional Commit messages.
Publish completed changes to `origin/dev` and open a PR to `main`; merging is a
separate action. Preserve the
[legacy archive](https://github.com/duckduckduck1/Mirage/tree/legacy-ansible-2026-10-23).

Before committing:

1. Stage only intended files, including new documents.
2. Run `python3 scripts/check.py` and `git diff --check`.
3. Review `git diff --cached` for secrets, misleading commands and unsupported
   claims. Checker errors report locations and categories, never matched values.
4. Describe the change, evidence and remaining limits in the PR.

The checker needs only Python 3.10+ and Git. It reads Git-tracked working-tree
files, including staged additions; ignored local files are outside its coverage.
No application installation or server credentials are needed for CI.

## Documentation and evidence

Use relative links between repository documents and direct links to official
upstream references. Explain where a command runs and whether it changes service
state. Do not copy the old deployment into new-install instructions.

Retain dated historical compatibility observations as historical evidence.
An untested clean install, backup delivery or migration must remain explicitly
untested. Update the [ledger](audit/acceptance-ledger.md) only with actual results.

Keep private infrastructure settings and operational recovery bundles outside the
checkout. Repository maintenance does not authorize accessing the running VPS.
