# Changelog

## 2026-10-27 — Effective XHTTP TCP timeout

- Set `GODEBUG=multipathtcp=0` for 3x-ui and its child core so the pinned runtime
  uses ordinary TCP and actually applies XHTTP `tcpUserTimeout=60000`.
- Preserved pinned images, data, user credentials, subscription bodies and the
  other containers; rechecked 16 HTTPS combinations and four XHTTP payloads.
- Verified closure of an isolated socket with unacknowledged response data after
  60.16 seconds, without restarting the production core during the test.
- Correlated the new CPU/memory alerts with bounded local history and documented
  host pressure separately from the container ceiling, including the first
  application rollback and the limits of isolated tests.

## 2026-10-26 — XHTTP peer timeouts

- Investigated accumulated idle XHTTP/REALITY sockets and the corresponding Xray
  goroutines during host-memory alerts; found no new container OOM or limit event.
- Applied native keepalive options only to XHTTP. Preserved all four
  users, transports, subscription bodies, bot settings and production containers.
- Rechecked 16 user/transport HTTPS combinations and four 256 KiB XHTTP payloads.
  Documented the initial rollback, native hot update and the remaining distinction
  between unreachable peers and healthy idle HTTP connections.

## 2026-10-26 — Local resource diagnosis

- Added a low-priority, standard-library sampler for host/process/container CPU,
  memory, OOM, throttling, swap, I/O and pressure counters every 15 seconds.
- Keep private, rotating JSONL history within 64 MiB with seven-day archive expiry.
  No new notifications, traffic logging, uploads or automatic VPN restarts.
- Added failure-path and attribution tests and documented interpretation and removal.

## 2026-10-26 — Legacy and staging retirement

- Removed the stopped Marzban, old Caddy and staging containers, their dedicated
  Docker resources and unused legacy images.
- Removed explicitly authorized old project/data/backup copies, retired recovery
  helpers and units, the cancelled observer, and the staging SSH account/key directory.
- Preserved production configuration, user credentials, subscriptions, bot settings,
  external recovery archives and shared ACME/DNS/SSH/MTU components. Verified four
  transports and all raw/JSON subscriptions without restarting protected services.
- Documented that local Marzban rollback and staging delivery are no longer
  available. Confirmed there is no CPU quota or observed CPU throttling.

## 2026-10-26 — Production memory limit

- Diagnosed an Xray kill as cgroup OOM at the inherited 320 MiB test limit;
  confirmed Marzban remained stopped and nightly archives came from the new timer.
- Increased the production 3x-ui ceiling to 512 MiB without restarting the
  container or Xray. Kept the isolated test example at 320 MiB and preserved
  the no-swap policy. Recorded the distinction between host and container pressure.

## 2026-10-25 — REALITY client compatibility

- Reproduced the bundled core's REALITY incompatibility with sing-box. Selected
  official Xray 26.7.28 through native 3x-ui management, retained the official
  application image, and persisted the verified core across container recreation.
- Corrected recovery inventory to inspect the managed core and preserve execute
  permission when archiving it.
- Rechecked all four users and transports, raw/JSON subscriptions and XHTTP
  payloads. Owner confirmed phone profiles, Throne after restart and video playback.
- Cancelled the temporary 48-hour observer and incomplete certificate continuity
  rehearsal at the owner's request; neither is reported as accepted.

## 2026-10-25 — Production migration to 3x-ui

- Moved four users and four transports to the reviewed official 3x-ui image on
  their original ports. Preserved VPN credentials; issued native subscription
  URLs without Marzban API/token compatibility.
- Verified every user/transport with HTTPS, both subscription formats, cold
  starts, container recreation and repeated XHTTP connections/exact payloads.
- Enabled the owner-only native Telegram bot and verified protected production
  secret delivery. Disabled plaintext native database delivery and temporary
  administrative API tokens.
- Moved ACME certificate output/reload to the new deployment and retained the
  stopped legacy data, images and hooks for rollback.
- Delivered encrypted data/images to Telegram, downloaded and restored that
  actual set in isolation, then rechecked production. Enabled daily 03:00 Saratov
  recovery delivery. Added private download receipts and corrected quoted ACME
  cron recognition in recovery archives.
- Recorded the approved bounded-memory test and its successful result without
  requiring a RAM upgrade. Real-client/TUN, certificate-change continuity,
  affected-network, foreign-account and observation checks remain separate.

## 2026-10-24 — VPS test preparation

- Staged separate test configuration and validated TLS copies, cached the official
  image and pinned Caddy to the observed working reference.
- Prepared restricted GitHub secret delivery and encrypted recovery material.
- Documented the insufficient concurrent-test RAM and the authorized sequential
  test procedure. Marzban remains running; 3x-ui has not started or been accepted.

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
