# Changelog

## 2026-10-23 — Documentation-first repository

- Replaced the Ansible deployment project and bilingual VitePress site with four
  English guides for using upstream Marzban.
- Removed installation roles, custom image build files and Node/Ansible tooling
  from the active branch. The old deployment remains available at the annotated
  [legacy archive tag](https://github.com/duckduckduck1/Mirage/tree/legacy-ansible-2026-10-23).
- Replaced the release gate with an offline, standard-library Python check for
  relative Markdown links and common accidental secret additions.
- Retired the documentation website in favor of repository Markdown.
- Kept previous acceptance evidence. The new setup has not received separate
  operational acceptance; the existing VPS was not migrated by this change.

## 2026-10-23 — Caddy certificate reload repair

Before archiving the deployment project, added forced Caddy reload to its TLS
hook. External certificate and subscription checks passed without restarting the
Marzban or Caddy containers. See the [ledger](audit/acceptance-ledger.md).

## 2.0.0 — 2026-07-28

- Replaced the original 3x-ui administration layer with Marzban.
- Added four inbounds, HTTPS subscriptions, Telegram administration and backups.
- Added Ansible installation/recovery scenarios and a bilingual documentation site.

The earlier application is preserved at
[`legacy-v0.1.0`](https://github.com/duckduckduck1/Mirage/tree/legacy-v0.1.0).
It is not compatible with the Marzban deployment.
