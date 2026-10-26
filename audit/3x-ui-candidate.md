# 3x-ui candidate review — 2026-10-24

[README](../README.md) · [Migration](../docs/migration.md)

Initial review scope: official v3.10.2 sources, public registry metadata and local
checks, without VPS access or bot messages. Subsequent authorized VPS preparation
is recorded separately below.

| Artifact | Observed value |
| --- | --- |
| 3x-ui index | `ghcr.io/mhsanaei/3x-ui:v3.10.2` |
| Index digest | `sha256:6c7e73c5bc4b6d7d70866616f78d6c9866b4904defad3077c1e2b5c1c89c2ec1` |
| Image source revision label | `608ef4e4010bf83e2e78328e08f77efc051ad4d7` |
| Checked platform | Linux amd64 |
| Extracted core | `Xray 26.10.10`, build `701af60`, Go 1.27.2 |
| Core SHA256 | `4cca4de3ab8c16b3803a70e9ebe0570d2a72480c716d89aa91603ec568bf0f44` |
| Upstream core commit | `701af60772cda123492f86e383e1fdba066614a9`, 2026-10-10 |
| Caddy candidate | `caddy:2.11.4-alpine` |
| Caddy index digest | `sha256:6aeddd44c3078b0f9a35206472a11420648a79c184603ef95957d0a20044cb2b` |

Local Docker daemon access required unavailable sudo authentication. Instead the verification
fetched the official image index, amd64 manifest and layers, verified their
SHA256 digests, extracted the core and ran **only** `version`. No proxy listener
or application container was started. The reported version matches
[DockerInit](https://github.com/MHSanaei/3x-ui/blob/v3.10.2/DockerInit.sh).

The Xray release/tag v26.10.10 returned 404, but its reported
[upstream source commit](https://github.com/XTLS/Xray-core/commit/701af60772cda123492f86e383e1fdba066614a9)
exists. This explains the binary's source reference; it is not an independent
reproducible-build verification or a reason to skip client compatibility tests.
The Caddy version is from the archived template, not a new server observation.

## Local repository checks

Sixteen tests passed with real age v1.3.2 encryption and OpenSSL fixtures:
SQLite WAL consistency, full bundle contents, contained archive paths, ciphertext
reassembly/corruption, resumable mocked delivery, bounded retention, certificate
validation/reload rollback, secret suppression and native-API request behavior.
Telegram, SSH and Docker calls were mocked; no real message was sent. Both normal
and egress-isolated Compose configurations and their exposure invariants passed
without a Docker daemon. Documentation/secret checks and Git whitespace checks
passed. These results do not replace container or server acceptance.

## Acceptance still pending at initial review

Actual container startup, native API/bot delivery, all user/transport tests,
subscription cold starts, GUI/TUN, TLS continuity, downloaded recovery restoration,
48-hour observation and production cutover remain pending. The current Marzban
results do not establish these properties for the candidate.

Subsequent results are recorded below; this paragraph describes the initial
artifact-only review.

## VPS preparation — 2026-10-24

- A fresh encrypted external recovery bundle contains the repaired Marzban core,
  a consistent SQLite snapshot with four users, both installed images, TLS/ACME,
  configuration and the four approved external maintenance scripts. Decryption,
  required members and SQLite integrity passed. Full restoration is still pending.
- Reviewed source, separate private test settings/data and a validated certificate
  copy were staged. Compose validation passed. Public bindings remain loopback.
- The official 3x-ui candidate was cached by the reviewed digest for amd64. Its
  extracted core on the VPS matched the SHA256 and version/build recorded above;
  only the binary's version command ran. The temporary unstarted inspection
  container was removed. No candidate service was started. The running Caddy reference is
  `caddy:2.11.4-alpine@sha256:5f5c8640aae01df9654968d946d8f1a56c497f1dd5c5cda4cf95ab7c14d58648`;
  the example now preserves this inventoried reference rather than the earlier
  template candidate listed above.
- All six test ports were free. Disk space was sufficient, but approximately
  304 MiB was available on an 888 MiB host, below the 512 MiB concurrent-test gate.
  The owner authorized a sequential test after preparation; memory must be
  rechecked after stopping Marzban. No stop or restart has occurred during preparation.
- A distinct SSH account/key permits only the exact staging secret receiver.
  A real authentication test reached its forced command; invalid input was rejected
  without changing settings. The private key was generated in memory and stored
  directly in GitHub, without a permanent local private-key file.
- All seven staging secret names are present. After owner Environment approval,
  the [manual delivery workflow](https://github.com/duckduckduck1/Mirage/actions/runs/40030510782)
  from merged `main` succeeded with `apply_bot=false`. On the VPS, Telegram
  confirmed the new bot token, its distinction from the legacy token, the owner's
  private chat and absence of a webhook. No message was sent or poller enabled.
- A separate consistent SQLite snapshot and private draft native API payloads
  contain all four active, unlimited, non-expiring users and all four inbounds.
  No per-user inbound exclusions were present. UUID/password, REALITY and
  transport settings were retained; only test ports and certificate paths differ.
  No tables were imported and no live database was modified. Runtime API and
  generated-subscription validation remain pending.
- Official age v1.3.2 was checked against its release asset checksum and installed.
  Its public recovery recipient was configured; the private identity was encrypted
  outside Git without plaintext persistence. A round-trip encryption test passed.
  An independent protected identity copy remains an owner task. No backup timer,
  DNS job, ACME hook or bot poller was enabled or replaced.
- Existing Marzban/Caddy container start times and restart counts remained unchanged.
  Staging files and image caching do not establish application, VPN or subscription
  acceptance.

## Controlled test and production switch — 2026-10-25

The owner approved replacing the original 512 MiB startup gate with a sequential,
bounded test: stop Marzban, retain the 320/64 MiB service limits without extra
container swap, and restore service on OOM, unexpected failure or less than
128 MiB host available memory. The test passed. The owner then explicitly
authorized the production migration without returning to Marzban.

### Native migration and compatibility

- Imported four active, unlimited, non-expiring users using native 3x-ui APIs,
  with one client per person attached to four inbounds. No Marzban tables were
  imported. Preserved UUID/password, REALITY keys/SID/SNI, client-version bound,
  flow, gRPC service name and XHTTP path/mode. Historical usage stays in the archive.
- Resolved the old server-IP placeholder to the actual advertised endpoint.
  Replaced the old `none` fingerprint sentinel with explicit `chrome`: the native
  JSON generator otherwise emitted an invalid REALITY client configuration.
- An initial empty-database startup raced with a simultaneous CLI migration.
  Reinitialized only the empty candidate database sequentially before daemon
  startup. This was a schema-initialization error, not evidence of insufficient RAM.
- Applied subscription listener settings with a cold restart. The panel is bound
  to host loopback; Caddy exposes only native `/sub/` and `/json/` paths.
- Native JSON uses simplified VLESS settings. Both the bundled Xray 26.10.10 and
  previous official client 26.7.28 successfully consumed it. The image/core match
  the reviewed identities; no custom core was installed.
- Retained the required private-address blocking rule and native API/statistics
  plumbing. Native default routing also blocks BitTorrent; this is an additional
  restriction compared with the inspected legacy rules.

### Transport and subscription evidence

- On alternate test ports, all four users × four transports passed real HTTPS
  traffic. Each user's XHTTP profile passed three additional connections and an
  exactly 1 MiB download. Both native subscription formats contained four profiles
  and matched private credentials, ports, REALITY keys, SID and SNI.
- Forced container recreation preserved native subscription IDs and user data.
  First and repeated subscriptions and all sixteen traffic combinations passed
  after recreation. Both reviewed client core versions passed the test matrix.
- After the authorized switch to original ports 443/8443/2053/9443 and subscription
  port 2096, all sixteen combinations passed again using client 26.7.28. XHTTP
  repeat/payload checks also passed for every user. Both TLS listeners served the
  trusted installed certificate; public panel/login paths returned 404.
- These are server-loopback client checks, not physical external-client tests.
  They do not establish Throne GUI/TUN reliability, phone XHTTP support, Beeline,
  campus Wi-Fi or mobile allowlist reachability.

### Resources and administration

- Measured approximately 124 MiB for 3x-ui/Xray and 16 MiB for Caddy, including
  their charged file cache. Minimum available host memory during the controlled
  test was approximately 207 MiB. No candidate swap, runtime OOM or unexpected
  container restart was observed after initialization. A RAM upgrade was not
  required for this measured workload; this is not a concurrency capacity claim.
- The owner confirmed the native bot's administrative menu and four users.
  Only the owner's ID is configured; friends remain unlinked. Native plaintext
  database delivery is disabled. Weekly reports and resource/core alerts are
  configured. A second-account administrative rejection test remains open.
- Distinct restricted SSH keys and owner-approved main-only Environments protect
  staging and production delivery. The
  [production delivery](https://github.com/duckduckduck1/Mirage/actions/runs/40175852874)
  succeeded with `apply_bot=false`, without a VPN or bot restart.
- Host acme.sh now installs the existing valid certificate into the new private
  TLS source directory and calls the managed publication helper directly. The
  old wrapper/domain configuration and both stopped legacy containers remain
  available for rollback. DNS updating and unrelated services remain in place.
- Publishing the current pair and forced Caddy reload passed. A genuinely changed
  certificate, Xray's delayed file reload and uninterrupted active transfer still
  need a separate continuity rehearsal. No such result is inferred from files
  or the unchanged certificate's successful TLS handshake.

### Downloaded recovery and handoff

- Delivered the official image archive in eight encrypted parts and the recovery
  archive in one part, with manifests and SHA256 checksums, to the owner's private
  Telegram chat. Downloaded those actual Telegram documents using private delivery
  receipts and verified every checksum. Retained an encrypted external copy.
- Decrypted on the workstation with the age identity held in memory. Verified
  SQLite integrity, four identities, required TLS/ACME/deployment state, image
  content hashes and the image-bundle reference. The private identity never went
  to the VPS; temporary local plaintext was removed.
- Loaded the downloaded matching image payload and restored separate data with
  verified image-ID tags. Initially blocked clone Internet egress and disabled
  its copied bot through the container-local native API before normal networking.
  Published host-port access was unavailable in the isolated network; the first
  probe attempt resumed production safely before that access method was corrected.
- Restored four subscription IDs and all private connection parameters. On the
  clone's alternate ports, first/repeated raw and JSON subscriptions passed,
  followed by sixteen HTTPS combinations, twelve additional XHTTP connections
  and four exactly 1 MiB downloads. Prepared-archive validation took about
  44 seconds; download/decryption and new-host provisioning are excluded.
- Stopped the clone, resumed production and repeated the same subscription/traffic
  matrix successfully. The production bot remained enabled; the clone's bot was
  disabled. Temporary administrative API tokens were disabled after checks.
- Enabled daily encrypted recovery delivery at 03:00 Europe/Saratov, with
  persistent scheduling and fifteen-minute failure retries. Initial real delivery
  and download were verified; the next scheduled run remains future evidence.
- Sent the new native raw/JSON links only to the owner through the new bot.
  No messages were sent to friends. Legacy containers remain stopped, and the
  temporary automatic legacy-return guard was completed.
- The owner confirmed successful import of the new subscriptions and connections
  from a real client. Exact client/build, transport and TUN/proxy mode were not
  recorded in that confirmation; it does not complete the detailed client matrix.
- Removed the temporary restore clone, test clients and plaintext restore inputs
  after successful checks. Private verification reports and encrypted recovery
  copies remain retained. The production containers were not restarted for cleanup.

### Outstanding operational acceptance

Verify the next scheduled delivery, test real clients, certificate continuity
and foreign-account permissions, and observe at least 48 hours and
the seven-day retention window. Do not remove the stopped legacy deployment
before those checks. The production switch does not complete the whole acceptance
matrix or prove reliability on restricted networks.


## Follow-up diagnostics — 2026-10-25

The temporary 48-hour observer was stopped at the owner's request. The certificate
rehearsal was cancelled before Xray's hourly file reload; uninterrupted renewal is
**not accepted**. A newly issued trusted certificate was published successfully
and Caddy served it without a container restart. Existing recovery data remains.

Reported client results supersede the earlier broad client acceptance: Trojan
works consistently, while TCP/gRPC REALITY fail in Throne, Hiddify and Karing;
XHTTP is intermittent in Throne. Previous same-core loopback checks did not cover
sing-box compatibility or the affected ISP path.

Isolated tests with the existing credentials reproduced a sing-box 1.13.16 TCP
REALITY failure against Xray 26.10.10 and 26.10.21. Both TCP and gRPC succeeded
against a separate official Xray 26.7.28 process. None of these isolated tests
changed the production core. See the [upstream compatibility report](https://github.com/SagerNet/sing-box/issues/4520).

Xray 26.10.10 was withdrawn upstream; [26.10.21 release notes](https://github.com/XTLS/Xray-core/releases/tag/v26.10.21)
record the CA security update. A compatibility version must be evaluated separately
from the current security release; a version change is not a general ISP fix.


### Applied compatibility correction and client recheck

- Selected official Xray 26.7.28 through native 3x-ui Core Management. Verified
  binary SHA-256 `64d46afb80adea1bf97a0d467e83f4a9ac1ebd0995891e84bca3f1a1d1affb1d`.
  The application image and user credentials did not change. Temporary API access
  was disabled after the change.
- Persisted the native managed core and required assets under the existing
  database volume using `XUI_BIN_FOLDER=/etc/x-ui/bin`. Recreated only 3x-ui and
  confirmed the same version, healthy container and no OOM/restart counter growth.
- After recreation, all sixteen user/transport HTTPS requests passed, all four
  raw/JSON subscription pairs passed, and all four XHTTP 1 MiB payloads had the
  expected length. The backup inventory reports the actual managed core.
- Tested archive/extract/execute of the managed binary with its exact checksum.
  Recovery preserves mode 0700 for executables and 0600 for ordinary private files.
  This is a targeted recovery check, not a new full encrypted-clone rehearsal.
- Clean laptop tests required routing mark `0x2024` to bypass the active Throne
  TUN. Binding only the Wi-Fi interface was insufficient; those earlier failures
  and timings are not evidence of an MTS block. The owner ran the bounded test
  locally with sudo. All seven engine/transport cases passed three HTTPS requests
  and an exact 4 MiB transfer; measured rates ranged from 1.76 to 12.11 Mbit/s.
  These short measurements do not establish sustained capacity or its bottleneck.
- The owner confirmed all phone profiles and normal latency. A full Throne restart
  and subscription refresh restored its two remaining profiles; the same Naruto
  episode then played normally. No local routing or Wi-Fi settings were changed.
- Both TLS listeners serve the newly issued leaf. This does not complete the
  cancelled active-connection certificate-rotation test. The observer stays off;
  existing size-limited container logs and daily recovery delivery remain.


## Cgroup OOM correction — 2026-10-26

At 10:39 Europe/Saratov the kernel killed Xray inside the production 3x-ui
container. The log identifies `CONSTRAINT_MEMCG`; `memory.events` records one
OOM and one kill under its original 320 MiB ceiling. This establishes a container
limit failure, not evidence that a second running Marzban exhausted host RAM.
Marzban, old Caddy and staging containers were stopped; only production services
and the unrelated media-bot workload were running.

Raised production memory and combined memory/swap limits to 512 MiB using
`docker update`. The container identity/start time and Xray PID were unchanged.
Before the change the host had about 362 MiB available. The private environment
now records the new limit; the shared Compose defaults to 512 MiB while the
isolated test example explicitly retains 320 MiB. No swap allowance was added.

After the change, actual HTTPS passed through each of the four transports and
all four raw/JSON subscription pairs passed. The OOM kill counter remained one,
the container was healthy and host available memory remained about 362 MiB.
This short check does not establish a long-term memory plateau.

The 03:00 three-part `Mirage recovery` delivery came from the new
`mirage-backup.timer`. An obsolete root cron entry referencing the old Marzban
backup was also removed, retaining a root-only rollback copy. The new timer,
ACME and DNS jobs remain; stopped legacy data is retained for rollback.


## Legacy and staging retirement — 2026-10-26

The owner explicitly authorized deleting the old installation, historical
Marzban/test recovery material and the separate staging SSH identity. Removed:

- Four stopped Marzban/old-Caddy/staging containers, three dedicated networks,
  four old Caddy volumes and both Marzban image references.
- The unused old operations image, legacy deployment/data directories, old
  project copies, previous-core audit copies and old admin-restore material.
- Five disabled legacy/temporary systemd units and their obsolete helpers,
  the cancelled observer and the staging account, home/key directory and sudo rule.

The root-owned staging home required explicit removal after `userdel` removed the
account but could not remove that directory. Current 3x-ui data, images, recovery
bundles and the independent workstation archives were preserved. Shared ACME,
DuckDNS, SSH safeguards and MTU configuration remain; this is not a global prune.

Post-cleanup comparisons passed for protected container configurations/identities,
start times/restart counts, Xray PID, production files, root cron, native user,
inbound and bot settings, and all eight raw/JSON subscription bodies. Actual HTTPS
passed through all four transports. Production backup/DNS timers remain active.
Mount lists were canonicalized for comparison because Docker inspect can reorder
them for the unchanged media-bot containers.

The dedicated Docker cleanup happened before historical file removal. Its first
raw mount-order comparison flagged a difference; subsequent inspection established
that the variation was only list order. The final canonical comparison passed.
No protected container was restarted. The source archive tag remains available;
there is no longer a local Marzban rollback installation or staging delivery target.

### CPU alert investigation

The host has one logical CPU. Docker CPU quota, NanoCPUs and pinning are unset;
`cpu.max` is `max 100000`, and throttled periods/time were zero. After cleanup, a
10-second sample measured about 8.82% for the 3x-ui cgroup and 23.66% host non-idle
activity (including about 0.20% I/O wait and 4.06% steal). Xray was the largest
current userspace consumer at about 5.39% in that sample.

The native Linux sampler reads aggregate `/proc/stat`; the bot compares that
percentage with its configured threshold. The reported 80% is an alert threshold,
not an enforced Docker cap. Historical 83–97% alerts cannot be attributed to one
process from current samples. No CPU quota or notification setting was changed,
and no daily monitor or automatic VPN restart was added.

## Bounded resource history — 2026-10-26

Installed `infra/resources.py` and `mirage-resources.service` independently of
Compose, following owner approval for local CPU/memory diagnosis. The unit passed
host `systemd-analyze verify`, is enabled/running and produces JSONL snapshots at
approximately 15-second intervals. It does not upload logs, send messages or
restart VPN services. Existing native bot alert thresholds remain unchanged.

The log directory is root-only 0700 and files are 0600. Rotation is bounded by
64 MiB total with 4 MiB segments and seven-day archive expiry; volume retention
can be shorter. Tests exercised rotation at reduced limits, private file handling,
PID reuse and CPU/OOM deltas. Resource JSONL files are ignored by Git.

The initial seven records included all four running containers. A separate
45-second steady measurement found about 0.98% of one CPU and 7.73 MiB charged
memory for the collector; its own service has a 64 MiB memory cap and low CPU/I/O
priority. These are short measurements, not a guarantee of future usage.

Protected container identities, start times, restart counts, images/configuration
fingerprints and the Xray PID were unchanged. Private production settings were
unchanged. No new host/container OOM increments or collector restarts were seen.
The root-only deployment/verification report is
`/var/lib/mirage-resources-deployment.json`. No historical spike is attributed to
a process on the basis of these new samples; future analysis must correlate the
recorded interval with process/cgroup counters and kernel/application events.
