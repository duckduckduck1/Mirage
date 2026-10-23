# Changelog

## 2026-10-24 — Official 3x-ui deployment candidate

- Replaced the untested fresh Marzban recipe with one Compose using official
  digest-pinned 3x-ui and Caddy images, isolated ports and private persistent data.
- Added bounded host tasks for encrypted SQLite/image recovery deliveries and
  validated TLS publication with forced Caddy reload, without a VPN restart.
- Added protected GitHub Environment token sources and manual verified-SSH
  delivery; no application fork, custom image build or permanent local token file.
- Documented native Telegram administration, acceptance, the seven-day observation
  period and matching-data rollback. Old Marzban subscription URLs are not promised
  compatible with 3x-ui. Historical evidence and archives remain intact.
- Kept source/artifact and local helper checks separate from VPS, client, TLS,
  restoration and uptime acceptance. No server migration is part of this change.

## 2026-10-24 — Existing-server Xray repair

- Recorded the approved upgrade of the existing pinned core to Xray v26.7.28,
  explicit REALITY client compatibility and public-key settings, with rollback
  copies retained privately. The Marzban A-13 image and subscriptions were kept.
- Recorded successful before/after subscription comparisons, all users' server
  traffic checks and external tests including an XHTTP 1 MiB download.
- Kept GUI/TUN, affected-network and fresh-install acceptance explicitly separate
  from these results. Replacing the panel remains a separate decision.

## 2026-10-23 — Existing-server checks and private recovery files

- Clarified that the Trojan installation example was chosen for a smaller draft
  and to avoid REALITY subscription handling, not for proven reliability in Russia.
  Working VLESS profiles remain part of the existing deployment.
- Recorded subscription and server-loopback transport checks separately from
  external client/network tests. Kept the new installation explicitly untested.
- Recorded a verified encrypted recovery copy, restricted data permissions and
  retirement of the obsolete 3x-ui backup timer without restarting VPN services.
- Documented local encrypted credential storage outside Git. Full restoration,
  network-specific failures and the separate old Certbot lineage remain unresolved.

## 2026-10-23 — Personal runbook

- Refocused README on installation, maintenance and recovery. Kept existing-server
  notes and historical evidence as secondary references.
- Chose one proposed fresh-install recipe: Ubuntu 24.04, official Marzban v0.8.4,
  Trojan TCP/TLS, native HTTPS subscriptions and acme.sh renewal.
- Removed contribution rules, the PR checklist and the unused Docker ignore file;
  ordinary documentation edits no longer require an acceptance-ledger entry.
- Wrote the guides as personal notes. Source review does not establish successful
  installation, renewal, restoration or client traffic; those tests remain pending.
- No server changes were made for this documentation update.

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
