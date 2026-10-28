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

## XHTTP idle peers and socket options — 2026-10-26

### Findings

Correlated the 18:33–18:34 Europe/Saratov host-memory alerts with the resource
history. Xray RSS grew from about 103 to 152 MiB around the event; the panel
remained in its earlier range. The container used about 245–257 MiB against its
512 MiB ceiling, with no new OOM or memory-limit event. In the ten minutes before
the diagnostic session, sampled memory pressure averaged below 0.8% over ten
seconds; CPU activity briefly reached about 81%, including host steal time.
The reported video slowdown was not objectively measured or attributed to RAM.

The final pre-change socket sample found 2,297 established connections on XHTTP:
2,293 idle in both directions for more than five minutes, including 1,308 for more
than half an hour. The dominant local pprof group contained 2,283 goroutines in
REALITY reads and `net/http.(*conn).serve`, waiting in `bufio.Reader.Peek` for
another HTTP request. No TCP keepalive timer was present on those sockets.

Some source addresses matched native online-user records. An address match does
not authenticate each idle connection or uniquely identify a person behind NAT.
The owner's Throne uses auto-selection; a causal link to its probes has not been
reproduced. Stable host consumers included fwupd at roughly 122–137 MiB RSS and
multipathd at roughly 27 MiB. Neither service nor the unrelated media bot changed.

One initial full-history analysis itself used about 50 MiB temporarily. Its timing
overlapped the 18:36 alert, so that interval is not used to attribute the original
event to VPN traffic. Later history reads stream records. A capped text heap
export was incomplete and is not used for live-allocation attribution; the useful
evidence is the bounded goroutine profile and selected runtime counters.

### Application and verification

The owner approved applying XHTTP socket timeouts with a short Xray restart and
rollback if checks failed. The initial full candidate passed native `run -test`,
and all four Base64/JSON subscription pairs were available. An API response-shape
correction was required before the first mutation; it did not restart the core.

The first applied configuration used idle=60 seconds, interval=20 seconds and
`tcpUserTimeout=60000`. A post-restart HTTPS probe failed and triggered the
prepared rollback. That initial harness did not retain its curl failure code;
the cause remains unclassified. All 16 user/transport combinations and four
256 KiB XHTTP payloads then passed on the restored configuration. Subsequent
application used native inbound hot updates without another forced core restart.

The first isolated dropped-peer rehearsal did not confirm closure within 150
seconds. The client remained alive, 54 packets were dropped inside its own network
namespace, and the temporary container/configuration were removed. Kernel socket
inspection then established that the listener used MPTCP (protocol 262) and did
not support `TCP_USER_TIMEOUT`; accepted sockets reported zero for that option.
The saved setting was therefore not accepted as evidence of enforcement.

Replaced that unsupported option with the native Linux custom socket option
`IPPROTO_TCP/TCP_KEEPCNT=3`, retaining idle=60 and interval=20. The final configuration
passed native validation, 16 user/transport HTTPS checks and four exact 256 KiB
XHTTP downloads with no recorded probe retry. All eight subscription bodies,
native credentials/attachments/settings and protected container identities,
start times and restart counts were unchanged. The maintenance API token was
disabled afterwards. The final native hot updates retained the core PID.

The database preserves the final options. Native hot update left the generated
config file unchanged; actual newly accepted socket options were inspected instead.
The previous accepted sockets still had their earlier values, so the same 60/20/3
parameters were applied once to 484 established XHTTP sockets, with no failures,
forced closes, global sysctl change or additional daemon. No other transport's
socket options were changed. Post-change core/container recreation was not part
of this check.

The corrected HTTP/1 idle rehearsal tracked a fresh socket inode, verified empty
send/receive queues and its actual 60/20/3 options, then blackholed only the
temporary client's network namespace. The target closed after 120.83 seconds;
the test client stayed running and the production core PID did not change.
This established idle-peer cleanup, not a bound on pending application data.
The HTTP/2 pending-data rehearsal remained open after 300 seconds with the
MPTCP listener. Temporary test containers and private configurations were removed.
Reports remain root-only under `/var/lib/mirage-netdiag/20261026-memory/`.

## Ordinary TCP and effective XHTTP user timeout — 2026-10-27

### Correlation of new alerts

Streamed the existing 15-second history rather than loading it into memory.
Intervals below use Europe/Saratov time; process maxima need not occur in the same
sample and are not added together.

| Interval | Observation |
| --- | --- |
| 03:00–03:06 | Recovery job ran for about 134 seconds and consumed about 86 CPU-seconds. The sampled Python peak was 79% CPU; the interval also included Xray traffic. |
| 12:06–12:14 | Xray peaked at 73% CPU, softirq worker at 16%, panel at 6%, host steal at 5%. Container CPU peaked at 76%; host available RAM stayed above 281 MiB. |
| 21:40–21:57 | Xray RSS peaked at 145 MiB, panel at 84 MiB, fwupd at 138 MiB. The VPN cgroup peaked at 251 MiB of 512 MiB; host available RAM fell to 164 MiB and memory `some avg10` pressure reached 12.05%. |

No host OOM delta occurred in these windows. There was no configured container
CPU quota. The evidence supports host CPU contention during the daytime alerts
and host memory pressure during the evening interval; it does not establish the
source or throughput of each user's traffic. fwupd and unrelated services were
left unchanged. The collector's sampled RSS was about 8 MiB. The original
application attribution remains incomplete for healthy idle pools.

### Authorized change

An isolated rehearsal with the exact pinned image and managed Xray binary had
confirmed that `GODEBUG=multipathtcp=0` exposes ordinary TCP and applies the native
user timeout to listener and accepted sockets. With explicit restart permission,
changed only the 3x-ui Compose environment and the XHTTP native socket options to
idle=60 seconds, interval=20 seconds and `tcpUserTimeout=60000` milliseconds.
Removed the superseded `TCP_KEEPCNT=3` custom option. Images, managed core, mounts,
512 MiB memory/no-swap policy and other inbound settings were preserved.

Saved a consistent SQLite snapshot and previous Compose/inbound settings for
rollback. The first attempt rolled back after the guard compared Compose's
configuration-hash label as immutable; that hash necessarily changes with the
environment. The corrected comparison excludes only that label, the generated
hostname and the intended environment variable, and retains all other checks.
Both attempts and the first rollback are recorded; neither is hidden by the
successful application report.

The second application completed at 22:03 Europe/Saratov. Kernel inspection of
the new XHTTP listener confirmed protocol=6, keepalive=1, idle=60, interval=20 and
`TCP_USER_TIMEOUT=60000`. The regenerated cold-start configuration matched native
settings. All 16 user/transport HTTPS checks and four exact 256 KiB XHTTP downloads
passed. All eight raw/JSON subscription bodies were unchanged, as were client
credentials, attachments, native settings and all other containers. The temporary
API credential was disabled.

The first post-change HTTP/2 blackhole rehearsal closed both fresh test sockets
within 85.42 seconds with the client still alive and the production core PID
unchanged. Accepted sockets had protocol=6 and user timeout=60000. Its 8 MiB
response had already been acknowledged before packet loss; the send queues stayed
empty. The report deliberately marks the pending-data requirement unconfirmed.
This result alone is evidence for idle-peer cleanup, not retransmission timeout.

A second, deterministic rehearsal first established an authenticated REALITY
HTTP/1 keepalive session on the same production XHTTP listener. It then suppressed
pure TCP ACKs only in that temporary client's namespace, sent another request,
and verified 104 bytes of unacknowledged response data on the fresh server socket
before blackholing the test namespace. The socket closed after 60.16 seconds;
the client remained running without OOM and the production core PID was unchanged.
Actual accepted options included protocol=6 and user timeout=60000. This verifies
the kernel retransmission timeout on that listener; the fixture is HTTP/1 and
is not claimed as a duplicate of the earlier HTTP/2 pending-data sequence.
Both temporary containers and private test configurations were removed.

The lasting application-level result still requires normal traffic evidence.
The initial restart reclaimed existing sockets; the resulting RAM decrease does
not prove that healthy idle pools are bounded. No automatic VPN restart, extra
notification, global TCP sysctl or unrelated-service change was added. Resource
history remains capped at 64 MiB; at the post-change check it occupied about
41 MiB, diagnostic files about 3 MiB, and the root filesystem had about 26 GiB
available. The collector and existing retention settings remain active.

The final 22:08 Europe/Saratov check found the panel healthy, the same post-change
core PID, 12 established XHTTP sockets and about 90 MiB charged to 3x-ui. Its new
cgroup recorded no OOM/limit events or CPU throttling. These are immediate
post-restart observations, not a long-term memory-growth measurement. Other
container identities/start times/configuration fingerprints were unchanged, and
`mirage-resources.service` remained active.

## Manual backup acceptance and nightly status — 2026-10-28

The owner authorized backup changes and a delivery test without restarting the
VPN, then explicitly chose to disable automatic backups. The first 03:00 attempt
that night had failed with a generic Python exception; its exact cause remains
unproven. The 03:17 retry succeeded. Neither attempt was an OOM or the two-hour
unit timeout. Review found that daily gzip level 9 repeatedly compressed about
173 MiB of managed core/geodata while the unit had no CPU quota.

Changed the helper to gzip level 1 and fixed stage names with UTC/elapsed timing.
Error records expose only exception/cause type and numeric errno/return codes
when available. They do not print error text, arguments, paths, response bodies
or credentials. Transient names are filtered before stat/open, including whole
temporary trees. The panel's atomically published metric file is copied through
one open inode before archiving. ACME validation ignores transient-file churn
but continues to reject actual account/configuration changes. Tests exercise
both cases, disappearing temporary symlinks, SQLite contents and private-log
redaction. These fixes address identified races without assigning an unrecorded
exception to one of them.

The manual unit uses `--force`, `CPUQuota=30%`, `CPUWeight=20` and `Restart=no`.
It reuses matching image bundles. `mirage-backup.timer` is disabled and inactive;
native plaintext bot backups remain disabled. Existing recovery material was
retained. Manual attempts still preserve resumable encrypted delivery.

One fresh recovery copy completed at 13:46 Europe/Saratov. Total logged runtime
was 58.431 seconds, with runtime-state archiving taking about 22 seconds. Three
available 15-second process samples showed CPU 29.24%, 19.72% and 5.00%, and
RSS about 18–23 MiB. These are sampled observations, not a measured instantaneous
maximum or a controlled same-load benchmark against the night run. The encrypted
copy was 58,480,210 bytes in four parts plus its manifest; all part checksums
matched and Telegram acknowledged delivery, including a stored manifest receipt.
The pre-existing image bundle was reused. No downloaded restore rehearsal was
performed for this test copy. A final logging-only refinement names the ACME
baseline stage separately; no second large delivery was needed.

Added a short-lived standard-library host check and systemd timer for one status
message at 03:00 Europe/Saratov. Native Telegram report scheduling in this version
is registered at panel startup; the separate job avoids a panel/VPN restart. The
existing native weekly report and alert settings remain unchanged. The host check
uses the same private token/recipient through the existing sender and does not
poll for updates. It checks x-ui/Caddy states, the production Xray process, local
panel HTTP, verified subscription TLS and four TCP listeners, plus available RAM.
It sends a warning on failed/incomplete checks. It has a 30% CPU quota, 64 MiB cap
and no automatic restart/retry. It neither probes authenticated VPN traffic nor
establishes reachability from Russian client networks. A complete host outage
also prevents its own status message.

The test status was delivered with all server checks passing. The timer is
enabled/active; its first scheduled run is 2026-10-29 03:00 Europe/Saratov. Both
one-shot jobs finished successfully. Final comparison preserved all five Docker
container identities/start times/configuration fingerprints/images, the production
core PID, client records, assignments and native settings. No VPN, panel, bot or
Caddy restart was requested. The safe verification report is root-only at
`/var/lib/mirage-backup-update-20261028/verification.json`.
