# Production review — 2026-11-11

## Scope and result

The production configuration, all repository guides and deployment records,
Compose, workflows and host helpers were reviewed after PR #58 merged. This review
used read-only production inspection and temporary, isolated clients/listeners.
The initial audit did not change production settings or restart services. The
subsequent authorized transport correction and host/helper changes are recorded
below. Temporary test processes and SSH forwards were removed.

The audit found a reproducible gRPC failure, a mobile-client compatibility
risk and limited host headroom. There is no evidence of a new container OOM or
continuous memory growth in the retained resource window. These are separate
findings; reducing notifications would not repair connection failures.

## Deployment before the correction

| Item | Observation |
| --- | --- |
| Application | Official 3x-ui v3.10.2 image, unchanged digest |
| Actual managed core | Official Xray 26.7.28, not the unused bundled core |
| Frontend | Official Caddy 2.11.4 image, unchanged digest |
| Capacity | One vCPU; 888.8 MiB usable RAM; swap configured on the host |
| VPN cgroup | 512 MiB memory ceiling; no extra swap allowance; no CPU quota |
| Accounts | Four enabled, unlimited, non-expiring clients; sixteen bindings |
| Runtime continuity | Same production core and container since October 27; zero container restarts |
| Legacy | Marzban and staging are absent |
| Scheduling | Automatic backups disabled; nightly status and resource sampling active |
| Storage | About 26 GiB free; resource history remains within its 64 MiB budget |
| TLS | Both public TLS listeners validate and expire on January 23, 2027 |

SHA-256 comparisons of the production Compose, Caddyfile and six relevant host
helpers matched the repository. No application fork or build was found. All five
stored maintenance API tokens were disabled. The default administrator name was
absent; TOTP is currently disabled despite its recommendation in Setup. The panel
is restricted to an SSH tunnel.

## 1. gRPC fails independently of Hiddify

The REALITY target for port 8443 is `www.uu.nl:443`. Its IPv4 endpoint refused TCP
connections from the VPS; the IPv6 attempt had no route. The same failure was
repeated rather than inferred from a single timeout. The resolved IPv4 endpoints
of the TCP and XHTTP targets accepted TLS 1.3 with HTTP/2.

Using the current credentials:

| Profile | Native Xray 26.7.28, VPS loopback | Hiddify core 5.5.5, through SSH |
| --- | --- | --- |
| VLESS TCP REALITY | Two HTTPS 204 responses | Three responses with hybrid; three with classical |
| VLESS gRPC REALITY | Two TLS failures | Three timeouts with each key-share mode |
| VLESS XHTTP REALITY | Two HTTPS 204 responses | Three responses with each key-share mode |
| Trojan TCP TLS | Two HTTPS 204 responses | Three HTTPS 204 responses |

The temporary Hiddify binary was downloaded from the official release and matched
its published asset digest. It reports core v5.5.5 and hiddify-sing-box
1.15.0-alpha.13. These are headless engine tests, not iOS/Android GUI or TUN tests.

### Prepared correction

An isolated gRPC listener reused the existing gRPC credentials, service name and
REALITY identity, with the reachable TCP target and matching SNI. Hiddify passed
three HTTPS requests and an exact 262,144-byte download. The first request took
6.049 seconds; subsequent requests took 0.227 and 0.259 seconds. This verifies a
functional candidate, not consistently fast cold starts or mobile reachability.

Apply the target, accepted server name and advertised server name together through
native 3x-ui configuration. Preserve credentials, short IDs, client bindings,
ports and subscription IDs. Existing clients must refresh to receive the new SNI.
Take a private rollback snapshot first. Do not patch only generated `config.json`.

## 2. Hiddify 5.5.5 needs its own acceptance

The reported failures now concentrate on Android/iOS Hiddify 5.5.5; Throne is
reported working. Hiddify documents a hybrid REALITY key share that enlarges the
ClientHello. Its tracker contains matching upgrade regressions. This is a plausible
network-dependent cause, not proof about this subscriber's MTS/mobile path.
[REALITY documentation](https://hiddify.com/core/sing-box/features/reality-hiddify/),
[release](https://github.com/hiddify/hiddify-app/releases/tag/v5.5.5),
[compatibility discussion](https://github.com/hiddify/hiddify-app/issues/2463).

Both hybrid and classical worked with the present 26.7.28 server through SSH for
TCP and XHTTP. A controlled phone comparison is still required. A profile-local
`tls.reality.key_share = "classical"` or share-link `keyshare=classical` is a test
candidate for this older server. It is not a universal setting for newer servers;
current Xray generations require the hybrid share. Changing the fingerprint alone
is not an established fix. Do not update the server core and alter key-share
behavior simultaneously.

Unavailable pings after enabling the VPN do not establish that tests are looping
through the VPS. TUN exclusions, probe routing, DNS, the test URL and handshake
behavior need a client log from the same event. No phone incident timestamp or
client log was available for this audit.

## 3. Subscription generation is responsive; mobile import remains unresolved

All four users were fetched twice in both raw/Base64 and Xray JSON formats with
a Hiddify user agent: sixteen HTTP 200 responses, four profiles each, 0.106–0.517
seconds per server-side HTTPS request. Current subscription and Trojan TLS validate.
This excludes a persistent generation failure at the observation time.

It does not establish reachability of the public subscription hostname/port from
an affected phone without a working VPN. It also does not validate a particular
QR payload, app deep link, stale saved URL or GUI import. The next import check
must separate DNS, TCP/TLS, HTTP download, parsing and connection testing, on the
same phone with VPN off and on. The present public HTTPS subscription port is
2096; a standard-port public endpoint is an optional design change that needs its
own port-sharing or address plan, not a port edit without dependency review.

## 4. RAM and CPU findings

The bounded collector retained 11,275 samples, from November 9 15:52 UTC through
November 11 15:35 UTC. Its volume limit provides about 48 hours here, not a full
seven-day history. Data was streamed and summarized in bounded memory.

| Metric in that window | Observation |
| --- | --- |
| VPN cgroup memory | 203.6–289.9 MiB, below 512 MiB |
| Xray peak sampled RSS | 143.7 MiB |
| Panel peak sampled RSS | 124.1 MiB |
| Host minimum MemAvailable | 138.2 MiB |
| New host/container OOM kills | Zero |
| VPN CPU throttling | Zero; no quota configured |
| Host activity | Mean about 26.8%; peaks reached 100% |
| fwupd peak sampled RSS | 190.3 MiB |

The displayed host activity includes I/O wait; the native panel's CPU calculation
excludes it. At major network peaks I/O wait was approximately zero, and softirq
accounted for roughly 43–61% of host CPU. Xray, kernel network work and occasional
panel work were the main correlated consumers. Process and softirq percentages
must not be added as independent costs: kernel work can be attributed in more
than one accounting view. There is no recorded traffic-rate history to assign
these peaks to a particular user, throughput or attack.

fwupd refreshes coincided with real memory pressure and swapping. On November 11
at 06:57:50 UTC, its sampled CPU was 33.8%, RSS about 150 MiB, host I/O wait 20%
and MemAvailable about 141 MiB. November 10 recorded a higher fwupd RSS peak.
Certbot still runs and fails against its old lineage; two nginx configuration
references remain. These jobs are separate from working host acme.sh renewal.
Do not remove their references or disable shared services without checking owners.
The unrelated media-bot containers were not the main resident consumers in these
samples; some of their anonymous memory is swapped out.

Memory repeatedly falls after activity. This window does not support a monotonic
leak claim. It does show limited host margin and episodic pressure. Removing an
unnecessary firmware-refresh workload could recover useful RAM; adding RAM alone
would not repair gRPC or mobile handshakes. If measured congestion persists after
cleanup, benchmark a larger CPU/RAM allocation rather than raising alert thresholds.

## 5. Old TCP/mux sessions remain

Two current snapshots found 928 then 856 established TCP REALITY connections.
825 were idle in both directions for over 30 minutes; a later snapshot counted
787 idle for over a day. No TCP keepalive timer was visible. XHTTP had no
established sessions at those snapshots. Absence of active XHTTP traffic limits
any comparison with its October failure.

A capped goroutine summary contained 4,546 goroutines, including several groups
of about 825 in Xray's mux dispatch, monitoring and pipe readers. This differs
from the earlier XHTTP HTTP-reader population. Source address counts do not
identify people behind NAT or prove the cause of retained sessions. There is no
continuous socket-count history to establish a monotonic accumulation rate.

Prepare native TCP keepalive and user-timeout settings on port 443, with the same
ordinary-TCP enforcement already verified for XHTTP. A listener hot update does
not change old accepted sockets. A single announced core restart can clear the
old population and apply settings consistently; it is not a maintenance strategy.
Keepalive will not bound peers that remain responsive. Inspect mux session
lifecycle and the client multiplexing settings before claiming a permanent fix.

## 6. Project review

### Availability checks do not test availability of each profile

`infra/status.py` checks process/listener/TLS presence, not authenticated traffic.
It can report a green server check while gRPC is unusable; its current message
states that limitation. Add bounded authenticated checks to the existing nightly
job, with explicit per-profile results and a time budget, rather than another
monitoring stack. Real phone/network acceptance remains separate.

The Compose panel healthcheck also lacks curl `--fail`, so an HTTP 500 response
can still exit successfully. Correct that in the repository for the next planned
recreation. Neither a panel healthcheck nor a status flag should trigger automatic
VPN restarts.

### Secret-delivery cleanup has a failure path

`infra/provision.py` issues an administrator token before discovering its numeric
ID. Failure during token listing or identification leaves `token_id=None`, so
its `finally` block cannot revoke it. Invalid port validation also occurs after
issuance. Current stored tokens were all disabled; this is a code failure-path
finding, not evidence of an active leaked token. Validate before issuance and
use a short native token expiry plus cleanup that covers discovery failures.

### Documentation and deployment defaults

The guides correctly distinguish test evidence and live deployment, but the first
installation path still starts from an old candidate image and a 320 MiB test
budget that already caused a production OOM. It is not a ready-to-use production
baseline. Separate the current supported procedure from migration/archive
material and maintain a dated client compatibility table. Add a short mobile
import/connect/reconnect procedure without protocol or editor choices.

3x-ui v3.11.0 is the current upstream stable release. It fixes security advisories
affecting v3.10.2; the fixed default-account issue concerns initialization, while
other published issues concern reverse proxies and WireGuard-family exports.
The present loopback panel, changed account and unused WireGuard features reduce
specific exposure; they do not make the old version current. Test a pinned
candidate image, API/helper compatibility, database migration and rollback before
upgrading. Re-evaluate the actual managed Xray separately.
[Release](https://github.com/MHSanaei/3x-ui/releases/tag/v3.11.0),
[advisories](https://github.com/MHSanaei/3x-ui/security/advisories).

Repository checks passed for 34 tracked files. The unit suite passed 24 tests;
two age integration tests were explicitly skipped because those local tools were
absent. Both normal and restore-isolated Compose configurations validate. These
checks do not test the phone application or an affected ISP.

## Recommended user experience

Use Trojan as the initial mobile baseline because it is the transport consistently
reported working. One subscription, one tested default and a connect button are
more appropriate for nontechnical users than asking them to interpret four ping
results. Keep alternative transports available for controlled testing and a
validated fallback; four transports on one IP do not provide independent service
redundancy.

Native client-to-inbound bindings can provide a Trojan-only mobile subscription
without a fork or custom generator. This would change which profiles appear in
that client's existing subscription, so decide the affected accounts before
applying it. Keep the owner's advanced desktop use separate where needed.
Do not remove a working alternative or force auto-selection merely for symmetry.

A mobile baseline is accepted only after fresh import with VPN off, first connect,
HTTP and video traffic, mobile/Wi-Fi transitions, sleep/resume and subscription
refresh on both Android and iOS. Test the actual default app configuration. A
headless engine pass is not a replacement for those checks.

## Application order

1. Save private native settings/consistent SQLite rollback material for the change.
   Keep automatic backup delivery disabled.
2. Apply the verified gRPC target/SNI correction and TCP socket settings through
   native configuration in one announced maintenance window. If a core restart
   is required, obtain the requested interruption approval first.
3. Recheck every account, both subscription formats and real HTTPS/payload traffic.
   Refresh one phone first and compare REALITY key-share behavior on its real
   network. Preserve the known-working Trojan path throughout the checks.
4. Review fwupd and the failed Certbot lineage dependencies, then retire only
   confirmed unnecessary work. Leave unrelated application containers and shared
   ACME/DNS/SSH services intact.
5. Agree the simple mobile profile set and prove fresh import/connect/reconnect
   before distributing it. Improve the existing nightly functional check and fix
   the repository findings. Test an application/core upgrade separately.

The following application record distinguishes completed work from the remaining
recommendations. No result guarantees uninterrupted service across every network.


## Applied transport correction — 2026-11-11

The owner authorized the gRPC target/SNI correction, TCP socket settings and an
Xray restart. A consistent SQLite snapshot passed integrity validation; original
native parameters, private subscription responses and protected-state digests were
saved root-only outside Git. Automatic backup delivery remained disabled.

### Application and rollback record

The initial full-config validator ran on the host, where the container's `/certs`
paths do not exist. Both the existing and proposed configurations failed that
host-path check. Validation inside the actual container passed before mutation.
This was a validation-environment mistake, not evidence of invalid production TLS.

The first application saved the intended native settings and restarted Xray. Its
socket guard searched `/proc/PID/net/tcp` only; the listeners were dual-stack
sockets in `tcp6`. The false failure triggered restoration of the original native
settings and another core restart. Read-only inspection confirmed all four
listeners and a healthy panel after rollback. The guard was corrected to inspect
both families and wait for listener readiness.

The second application completed at **20:13 Europe/Saratov**. Including the first
application and rollback, there were **three core restarts**, rather than the
single restart originally intended. No panel, Caddy or other container restarted.
Both attempts are retained in the maintenance record.

### Effective configuration

- gRPC on 8443 now uses the same verified REALITY target and matching accepted and
  advertised SNI as TCP. Its credentials, private/public keys, short IDs, service
  name, port and client bindings were preserved. Clients need a subscription
  refresh for the changed gRPC SNI; subscription URLs remain unchanged.
- TCP REALITY on 443 now has native `tcpKeepAliveIdle=60`,
  `tcpKeepAliveInterval=20` and `tcpUserTimeout=60000`. Cold-start output and
  kernel options were checked. Both the listener and an accepted socket reported
  protocol 6, keepalive enabled and the exact intended values. Dual-stack IPv6
  socket representation does not mean MPTCP is enabled.
- XHTTP and Trojan native settings, image/core versions, limits, users, bindings,
  panel/bot settings and all container configurations remained unchanged. Only
  the intended gRPC SNI difference was allowed in subscription comparisons.

### Verification

- All four accounts through all four transports passed native-client HTTPS:
  **16 of 16**. gRPC requests took 0.221–0.286 seconds in these loopback probes.
- Each account passed an exact 256 KiB XHTTP download: **4 of 4**.
- First and repeated raw/JSON subscription fetches passed: **16 of 16** after
  cold start. Raw and JSON both advertised the new gRPC SNI; remaining body
  parameters matched the private before-change baseline.
- Official Hiddify core 5.5.5 passed **21 HTTPS requests** through SSH: three for
  each REALITY transport with hybrid, three with classical, and three for Trojan.
  These used a temporary local SOCKS listener without TUN or route changes.
- The temporary maintenance API credential was disabled; all temporary probe
  processes and forwards finished. The original version pins were rechecked.

An immediate post-change sample found approximately 189 MiB charged to 3x-ui,
302 MiB host available RAM and 128 core file descriptors. TCP had 26 established
connections, all with keepalive timers; none was idle for five minutes yet. The
container remained healthy, with zero new OOM/limit events and no recreation.
These values follow a restart and tests; they do not prove a memory plateau,
healthy mux-pool bounds or sustainable throughput.

The existing bounded resource collector and nightly status timer remain enabled.
Automatic backups remain disabled. Firmware/Certbot jobs, notification thresholds,
profile membership and application/core upgrades were not changed in this window.
After refreshing the existing subscription, the owner confirmed that TCP and
gRPC both opened a website on one phone using Hiddify 5.5.5 with manual selection.
The exact phone OS and network were not recorded in this confirmation. Fresh
import, both mobile platforms, network transitions and the reported post-connect
auto-selection behavior remain separate acceptance checks.


## Applied host cleanup and helper fixes — 2026-11-11

The owner requested host-level investigation and continuation of the review fixes.
This work did not restart Xray, 3x-ui, Caddy or unrelated application containers.
All container configurations, PIDs, start times and restart counts matched the
private before-change snapshot. Bot settings, users and subscription URLs were
preserved. Root-only rollback metadata for host job states and previous helper
files was retained outside Git; automatic backup delivery stayed disabled.

### Confirmed background jobs

This host reports KVM virtualization. fwupd listed one internal device without an
updatable flag, no update history, no active refresh and no application dependency.
Its service, refresh service and timer were stopped/masked. The old Certbot timer
and service were masked after confirming disabled/inactive nginx, one obsolete
lineage, no container mounts or active application references to that lineage,
and the current acme.sh certificate-publication hook. Certbot's packaged cron
entry is guarded out on systemd hosts. Certificate files and packages were kept.
OS security update timers, shared ACME/DNS/SSH and storage services were retained.
These host-specific decisions are not a generic installation recipe.

Immediate MemAvailable increased from **281.7 to 352.6 MiB**; used swap decreased
from 250.3 to 192.1 MiB. These are separate snapshots under ongoing traffic, not
unique-memory accounting or a controlled capacity benchmark. Removing fwupd also
removes the measured firmware-refresh workload and its later D-Bus reactivation.

### Bounded diagnostics and functional status

The existing collector now adds schema-2 uplink byte/packet/error/drop deltas,
softnet processed/drop/time-squeeze counters, production transport TCP state
counts, and core/panel FD counts. It always retains panel/core samples even when
other processes lead CPU/RSS rankings. PID identity changes discard in-progress
socket measurements; network counter resets/new observations yield null deltas.
No peer addresses, client ports or payloads are retained. The same 15-second
interval, private files, 4 MiB rotation and **64 MiB total budget** remain.
Only this collector service restarted. It used about 8 MiB charged memory at
verification. Network and connection history starts here; earlier CPU peaks
cannot be assigned retroactively to packets, a user or an attack.

The existing 03:00 status job now fetches and validates one enabled client's JSON
subscription and makes a real HTTPS request through each transport. Sequential
short-lived clients use the persisted binary verified against the live core.
Children are cleaned up on failure/timeout. A missing profile, low memory or failed
request cannot produce a green status. This is one-account VPS-loopback evidence,
not an ISP or mobile-client acceptance test. The existing daily message schedule
and recipient remain unchanged; no continuous probe or automatic restart was added.

A transient acceptance run with **CPUQuota=30% and MemoryMax=96 MiB** passed all
four authenticated HTTPS checks, TLS, subscription content, processes and ports.
It ran for 10.392 seconds and used 2.888 CPU seconds. No Telegram message was sent.
The status job's former 64 MiB limit was raised only for its bounded child clients;
the production container's memory/CPU limits were unchanged.

### Credential cleanup and repository defaults

Secret delivery now validates the local port before issuing a credential. The
native CLI creates a unique invocation token into a captured pipe; the helper
sets its five-minute native-table expiry before API use and removes that exact
owned credential independently of API availability, including malformed CLI
output or caught failures. This uses the reviewed api_tokens schema only: no
user/settings table is written directly. The CLI has no expiry flag. Abrupt death
between issuance and arming expiry still needs private inspection; the scheme
cannot promise cleanup under every process/power failure.

Live verification accepted the temporary token, then rejected it after cleanup;
the stored token count and bot/settings digest were unchanged. Tests cover port
rejection, malformed output, issuance failure, expiry and independent cleanup.
The Compose healthcheck now includes curl --fail in the repository. It is not yet
active in the existing container: applying a changed healthcheck requires the
next announced recreation. No recreation was performed for this low-impact fix.
The isolated example now uses 512 MiB rather than the failed historic 320 MiB cap.
Existing private production settings were not rewritten.

### Post-cleanup sample and remaining limits

Between 16:26 and 16:37 UTC, 41 retained samples recorded available host RAM of
348–374 MiB, VPN cgroup memory of 192–223 MiB, mean host CPU activity of 22.6%
and a maximum of 58.9% excluding I/O wait. There were no host OOM increments or
VPN throttling/limit events. Some page-ins/page-outs and a transient memory PSI
avg10 maximum of 2.43 remained; zero memory pressure is not claimed. The interval
includes the authorized diagnostic probes and is not comparable load to the
entire earlier 48-hour window.

The final sample had about 357 MiB available RAM, Xray RSS 50 MiB, panel RSS
129 MiB and 165 core FDs. Established sockets were TCP 11, gRPC 2, XHTTP 1 and
Trojan 45. This small population after the earlier core restart does not prove
long-term pool bounds. Interface and softnet drop deltas were zero in the latest
interval; one softnet time-squeeze increment occurred. Cumulative older drops
cannot be dated from that snapshot. Root free space was about 25.75 GiB and
resource history occupied 58.4 MiB within its existing budget.

The remaining major CPU finding is kernel network processing alongside Xray on
one vCPU. No CPU quota/throttling was found to remove. The new counters enable
correlation at the next real spike; do not attribute all old peaks to fwupd or
promise that legitimate traffic can never saturate the CPU. If sustained pressure
continues after this cleanup, compare the same workload on a larger allocation
before changing alert thresholds or imposing a VPN CPU quota.

Local checks: 35 tests ran, with 33 passes and two explicit age-tool integration skips;
documentation/secret checking and both Compose renderings passed. Phone evidence
remains limited to the previously reported TCP/gRPC result. Application/core
upgrades, broader mobile import/auto-selection acceptance and certificate rotation
under a continuous VPN transfer remain separate planned work.
