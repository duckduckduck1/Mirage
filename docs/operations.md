# Operations

[README](../README.md) · [Setup](setup.md) · [Recovery](recovery.md) · [Migration](migration.md)

**Status: 3x-ui production switch completed on 2026-10-25.** Legacy Marzban
and staging resources were removed on 2026-10-26.
Remaining acceptance checks are recorded in the [deployment review](../audit/3x-ui-candidate.md).

## Telegram administration

Use a separate native 3x-ui bot with the owner's numeric Telegram ID as the sole
administrator. Do not reuse the Marzban bot token, link friends' Telegram IDs or
distribute bot invites. Unlinked accounts can request their ID; verify that they
cannot perform administrative actions. Native user self-service is not configured.

The bot provides status, client creation, subscriptions and QR codes. Create one
client per person attached to the four accepted inbounds, with explicit quota
and expiry. Distribute links privately. See the
[upstream bot guide](https://github.com/MHSanaei/3x-ui/blob/v3.10.2/docs/content/docs/en/operations/telegram-bot.mdx).
Only one instance may poll a token.

Weekly reports run Sunday at 10:00, Europe/Saratov. Enable Xray crash and CPU/memory
alerts. Outbound events require configured, tested probes. Keep automatic restart
on probe failure disabled: a transient external failure must not restart all
connections. Health checks measure the panel listener, not end-to-end VPN traffic;
unhealthy status alone does not trigger Docker's restart policy.

### Nightly server status

At **03:00 Europe/Saratov**, [mirage-status.timer](../infra/mirage-status.timer)
runs a small [host check](../infra/status.py) and sends one message to the same
private administrator chat. It checks the two container states, the Xray process,
the local panel, the subscription TLS certificate and four listening TCP ports.
It fetches one enabled client's native JSON subscription over verified HTTPS and
uses the running core binary in sequential, short-lived clients to request HTTPS
through each profile. Credentials stay in memory; probe processes are terminated
after each request. It includes available host RAM. A failed check sends a warning instead of a
success message; a failed Telegram send is recorded as a delivery failure.

The test requires the four configured transports in that subscription and at
least 128 MiB host available RAM. An absent client, missing profile, malformed
response or low memory cannot produce a success message. It tests one account
from VPS loopback and an external HTTPS target, not all users or reachability
from a client ISP. Target outages can also fail the check; compare a second target
manually before changing the VPN. The native weekly report remains unchanged. No extra bot, continuous
monitor, traffic logging or VPN restart is involved. The native Telegram report
schedule is registered at panel startup, so changing it alone cannot activate a
new schedule without restarting the panel in this version.

```bash
sudo install -m 644 infra/mirage-status.service infra/mirage-status.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mirage-status.timer
sudo systemctl start mirage-status.service
```

The status service and its children are capped at 30% of one CPU and 96 MiB; it has no automatic
retry. A complete VPS outage also prevents its message. Missing nightly status
is a reason to check, not independent proof of VPN failure. Immediate host-down
detection requires an external monitor.

For a diagnostic run without a Telegram message, use a transient unit:

```bash
sudo systemd-run --unit=mirage-status-check --wait --pipe --collect \
  -p CPUQuota=30% -p CPUWeight=20 -p MemoryMax=96M -p RuntimeMaxSec=2min \
  /usr/bin/python3 /opt/mirage/infra/status.py --config /etc/mirage/host.json --check-only
```

Running Python directly bypasses the unit's limits. A check
does not restart production Xray or alter profiles, routes or subscription URLs.

## Secret management

GitHub Environment Secrets are the canonical token source. No permanent plaintext
token files are required on the workstation. Runtime copies remain necessary in
root-only VPS files and the 3x-ui database. GitHub cannot return stored values
through its API; delivery must run inside an explicitly authorized Actions job.
Vault is not required for this deployment.

`vpn-staging` and `vpn-production` allow only `main` and require owner approval.
Existing credentials are stored in production as `LEGACY_TELEGRAM_BOT_TOKEN` and
`DUCKDNS_TOKEN`. The legacy Telegram secret is not consumed by the new workflow.
Historical encrypted recovery archives are retained separately.
The original targets used separate restricted SSH identities. The staging account,
key directory and sudo rule were removed on 2026-10-26; `vpn-staging` remains in
GitHub but cannot deliver until a new test host/account is explicitly prepared.
Production delivery and its restricted identity remain configured. Delivery was
verified on 2026-10-25 with `apply_bot=false`; it left the running bot and VPN up.

Enter these values directly in GitHub Settings → Environments:

| Secret | Purpose |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | New bot dedicated to 3x-ui |
| `TELEGRAM_ADMIN_ID` | Positive personal administrator chat/user ID |
| `SSH_HOST`, `SSH_PORT`, `SSH_USER` | Prepared delivery account |
| `SSH_PRIVATE_KEY` | Dedicated restricted key, not the personal administration key |
| `SSH_KNOWN_HOSTS` | Independently verified host key with correct port syntax |
| `DUCKDNS_TOKEN` | Production DNS/ACME credential; absent in staging |

Create the bot through BotFather and start its private conversation. Never place
its token in an issue, command argument or checkout. Store the age recovery
identity in an independent protected store/password manager, never on the VPS
or in Telegram.

In [BotFather](https://t.me/BotFather), send `/newbot`, choose a display name and
an available username ending in `bot`. Add the returned token directly to
`vpn-staging` as `TELEGRAM_BOT_TOKEN`; do not send it through chat. Open the new
bot and press **Start**. Configure the owner's verified positive numeric ID as
`TELEGRAM_ADMIN_ID`. See the [official token instructions](https://core.telegram.org/bots/tutorial#obtain-your-bot-token).

### Manual delivery

The [delivery workflow](../.github/workflows/secrets.yml) runs only by manual
dispatch from `main`, after environment approval. It does not install, migrate,
renew certificates or restart the VPN. PR checks have no runtime secrets.
The workflow must first be merged into `main`. If a run waits for protection
approval, open **Review deployments**, select the requested Environment and
approve it as its designated owner. Do not remove branch/reviewer protections
to bypass that gate.

Before dispatch, separately authorize host preparation. Install a root-owned
checkout at `/opt/mirage` and prepare private Compose/host settings. Verify SSH
host identity independently; do not trust an unverified `ssh-keyscan` result.
Restrict the dedicated key with `restrict` and a forced command:

```text
sudo -n /usr/bin/python3 /opt/mirage/infra/provision.py --receive staging
```

Use `production` for the production key. Grant sudo only for that exact command;
no arbitrary shell, forwarding or general root access. Use distinct restricted
keys for the two targets.

With `apply_bot=false`, the workflow updates prepared root-only host settings and,
in production, `/etc/mirage/secrets/duckdns_token`. It does not edit or run DNS/ACME
jobs. Wire that credential path to the existing consumers only during the approved
migration. Unprepared or mismatched targets are rejected.

With `apply_bot=true`, it also applies Telegram settings through the native panel
API on host loopback, preserving other settings. The native CLI supplies a named
temporary API token into memory. Each invocation uses a unique reserved name.
On the reviewed v3.10.2 schema the helper sets a five-minute expiry immediately
after issuance and removes only that invocation's credential in a `finally`
block, including CLI-output/API failures. This narrowly scoped SQLite credential
cleanup is needed because that CLI has no expiry flag; it never writes user or
settings tables. Cleanup does not depend on the API being reachable. An abrupt
process death between issuance and arming expiry remains a cleanup risk; inspect
reserved credentials after an interrupted delivery. Schema changes require review
before an application upgrade. Telegram
values travel in an HTTP body, not process arguments. This path was tested with
the installed image; the owner confirmed the administrative menu and four users.
Enabling the bot can send native messages.

SSH key files exist only in the runner's private temporary directory and are
removed afterwards. Errors suppress SSH/API output. For rotation, change the
provider token, update the Environment secret and repeat delivery. GitHub outages
do not stop an already configured VPN.

## Status and logs

From `/opt/mirage` on the authorized host:

```bash
sudo docker compose --env-file /etc/mirage/compose.env ps
sudo docker compose --env-file /etc/mirage/compose.env logs --since 1h --tail 100
sudo journalctl -u mirage-backup.service --since '1 day ago'
```

Inspect logs privately; they may contain addresses or client links. Production
host settings are `/etc/mirage/host.json`, Compose settings are
`/etc/mirage/compose.env`, and data is `/var/lib/mirage`. The test equivalents are
`/etc/mirage-test` and `/var/lib/mirage-test`; the previous installation at those
paths was removed on 2026-10-26.

## Certificates

Existing host-level acme.sh remains the sole renewal owner. Container ACME is
disabled. Both services mount the entire TLS parent directory read-only so atomic
`current` symlink changes remain visible. Use a trusted system CA store in
production (`ca_file=null`); custom test CAs are for isolated fixtures only.

The production ACME reload command is:

```bash
/usr/bin/python3 /opt/mirage/infra/tls.py --config /etc/mirage/host.json \
  --certificate /var/lib/mirage/tls-source/fullchain.pem --key /var/lib/mirage/tls-source/key.pem
```

Check every certificate consumer before
changing existing output locations. The helper validates hostname, trust, expiry
and key match; publishes a versioned pair; and forces Caddy reload. Failed reload
restores the old pair and attempts recovery reload. Telegram failure notification
is attempted when configured. No VPN restart is requested. `--publish-only`
bootstraps a pair without Docker or Telegram access.

Production acme.sh installs its pair into `/var/lib/mirage/tls-source/` and calls
the helper directly with `fullchain.pem` and `key.pem`. Renewal no longer depends
on Marzban directories or its restart command. Legacy renewal rollback copies
were removed with the old installation on 2026-10-26. The production ACME account,
certificate source and reload command above remain in use.

Test Trojan's file reload against the candidate core. The previously reviewed
Xray implementation polls hourly by default: allow 65 minutes for rehearsal,
compare served leaf fingerprints on both TLS listeners and maintain an active
transfer. Files on disk alone are insufficient. This changed-certificate continuity
test remains open after the explicitly authorized production switch; publishing
the existing valid pair and checking both listeners does not establish it.
Automatic restarts are not a fallback for a failed renewal test.

## Encrypted backups

**Automatic backups are disabled by owner choice.** The old
`mirage-backup.timer` is disabled and inactive. Existing encrypted archives and
keys are retained; the manual backup service remains available.

`infra/backup.py` takes a consistent SQLite snapshot, checks integrity and encrypts
with age before delivery. Plaintext native bot backups remain disabled. The task
checks running image identities/data mounts and records the actual core version.
It retains the managed core and geodata needed for offline restoration.

Compression uses **gzip level 1**. Transient files and directories are filtered
before stat/open; panel metric history is copied from one open inode before
archiving, preserving a published snapshot during upstream atomic replacement.
TLS publication is locked during its snapshot. Changes to non-transient ACME
state invalidate the snapshot; temporary-file churn alone does not.

The manual unit has `CPUQuota=30%` and `CPUWeight=20`. It has no automatic restart
or retry. A CPU quota limits the job's CPU time, not total host load; other traffic
can still saturate this one-vCPU VPS. Lower compression can enlarge the archive;
measure actual duration/size rather than assuming a fixed saving.

Configure a valid age public recipient in the private host JSON. Install/update
the service and deliberately keep scheduling off:

```bash
sudo install -m 644 infra/mirage-backup.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl disable --now mirage-backup.timer
sudo systemctl start mirage-backup.service
sudo journalctl -u mirage-backup.service --since '10 minutes ago'
```

The service uses `--force` to create a fresh recovery copy even if one was already
delivered that day. Matching image bundles are reused. Running the helper directly
with Python bypasses the unit's CPU controls. Running it directly
without `--force` skips an already completed same-day copy. `--include-images`
also exports the images again; reserve it for a deliberate image archive.
`--prepare-only` encrypts and queues without contacting Telegram and does not prove
delivery. A manual attempt resumes pending delivery before creating another copy.

Stage logs contain UTC timestamps, elapsed time and fixed stage names. Failures
record exception/cause types and numeric errno/return codes when available, without
exception text, file paths, arguments, tokens or response bodies. Stages distinguish
snapshot, archive, encryption, splitting and delivery. The exact first-failure
cause on 2026-10-28 cannot be recovered from the earlier generic log.

The existing delivery format remains: parts at most 18 MiB, SHA256 hashes and a
final manifest. A recovery copy also references a separate image bundle. This is
why one backup produces several Telegram documents; disabling automatic backups
stops those routine deliveries. Retries of a manual command skip acknowledged
parts, though acknowledgement-boundary failures can produce identifiable duplicates.

Only delivered recovery copies older than seven days are pruned locally, during
a manual run. Queued parts and image bundles are retained. A power loss may leave
private `.snapshot-*`, `.images-*` or `.queue-*` directories; remove only confirmed
abandoned task directories. Existing archives are not removed by disabling the timer.

## Updates and failures

Save matching images/data, test a candidate digest and bundled core in isolation,
then explicitly pull and recreate services in an agreed window. Keep unattended
image and core updates disabled. Repeat subscription,
traffic, TLS and recovery checks after changes.

### Core compatibility

Production uses official **Xray 26.7.28** selected through native 3x-ui Core
Management. The binary SHA-256 is
`64d46afb80adea1bf97a0d467e83f4a9ac1ebd0995891e84bca3f1a1d1affb1d`.
It is a pinned compatibility version, not the latest security release.
Xray 26.10.10 was [withdrawn upstream](https://github.com/XTLS/Xray-core/releases/tag/v26.10.21);
26.10.21 fixes the reported CA issue but still rejects the tested sing-box REALITY
handshake. See the [compatibility issue](https://github.com/SagerNet/sing-box/issues/4520).

The official application image remains unchanged. `XUI_BIN_FOLDER=/etc/x-ui/bin`
in the private Compose environment points native core management at the existing
persistent database volume. The directory contains the verified official binary,
matching GeoIP/GeoSite assets and the generated private runtime configuration.
It must be populated and checked before changing the variable; an empty directory
cannot run Xray. The example keeps `/app/bin` as its image-default path.

The managed directory is included in encrypted recovery snapshots. The backup
helper probes the configured binary rather than reporting the unused image core.
Restore this directory and its private environment together. Recreating 3x-ui must
preserve both the core version and users. Native version changes restart Xray;
prepare rollback first. Do not build a custom core or silently switch to latest.

| Symptom | Checks |
| --- | --- |
| Everyone disconnects | Restarts, OOM, disk, reboot and renewal timestamps |
| Subscriptions fail, cached profiles connect | Caddy, certificate and subscription listener |
| One client fails | Version, imported fields, routing and TUN/proxy mode |
| One network fails | Same device/profile on another network; correlated logs |

TCP connection, profile import and ping are not sufficient traffic evidence.
Several transports on one IP do not provide an independent IP fallback.

### Mobile import and acceptance

Use the existing private subscription URL, not a single transport's QR code.
On a test phone, disconnect other VPN applications, import that subscription
once in Hiddify and wait for its profiles. Do not distribute links publicly or
create repeated duplicate imports after a timeout. If import fails, record the
app error, time and Wi-Fi/mobile network; check HTTPS subscription delivery
separately from VPN authentication.

For a controlled baseline, select Trojan manually, open a website and play video.
Then test TCP and gRPC individually. Check XHTTP on the actual app before relying
on it. Finally test sleep/resume, mobile/Wi-Fi transitions, reconnect and updating
the existing subscription. Test auto-selection only after the individual profiles
work. A test changes no server bindings; friends' default profile set has not been
reduced or accepted as a new configuration.

| Client evidence | Date | Scope |
| --- | --- | --- |
| Hiddify 5.5.5 phone | 2026-11-11 | Owner confirmed TCP/gRPC website traffic after refresh; OS/network not recorded |
| Official Hiddify core 5.5.5 | 2026-11-11 | All transports through SSH; no mobile GUI, TUN or ISP coverage |
| Throne desktop | 2026-10-25 | Owner confirmed TCP/gRPC and video after restart; historical result |

Fresh import on both iOS and Android and post-connect auto-selection still need
device evidence. The nightly VPS check cannot establish these results.

### Memory limits

Production and the isolated test example set `XUI_MEMORY_LIMIT=512m`.
The same value applies to memory and combined memory/swap, so the container has
no swap allowance. This is a ceiling, not a reservation of host RAM.

On 2026-10-26 at 10:39 Europe/Saratov, a cgroup OOM killed Xray under the original
320 MiB limit. The kernel recorded `CONSTRAINT_MEMCG` and `oom_kill=1`. Marzban
was stopped; the 03:00 recovery delivery came from `mirage-backup.timer`.

Check both container `memory.events` and host `MemAvailable` before attributing a
kill to the VPS size. `signal: killed` alone does not identify the cause. Existing
OOM counters and Docker's OOM flag remain historical evidence after a live limit
change; compare timestamps and counter deltas to identify a new event.

The limit can be increased on the running container with `docker update`, without
restarting Xray; keep the private environment and Compose configuration consistent.
Do not disable the OOM killer or add automatic VPN restarts to hide memory pressure.

### Host background jobs

The 2026-11-11 host review found firmware refresh activity consuming up to
190 MiB sampled RSS and coinciding with swap/pressure. On this KVM VPS, fwupd
reported no updatable devices and no update history. Its service, refresh service
and timer were masked after checking dependencies. The obsolete Certbot service
and timer were also masked: nginx was disabled/inactive, no container mounted
its lineage, and production renewal belongs to the existing acme.sh hook.
Certificate files and packages were retained; no VPN container restarted.

Available RAM increased from about 282 to 353 MiB in immediate snapshots. This
is workload-dependent headroom, not a permanent capacity guarantee. Security
update timers and unrelated application containers remain enabled. Do not copy
these service masks to a different host without checking its dependencies.
The [production review](../audit/production-review-2026-11-11.md) records verification
and the remaining one-vCPU capacity limit.

### XHTTP connection cleanup

The 2026-10-26 investigation found about 2,300 established XHTTP sockets; almost
all were idle in both directions for more than five minutes. A local goroutine
profile showed the dominant group waiting for the next HTTP request. This is
distinct from hitting the container's 512 MiB ceiling: no new OOM or limit event
was recorded during the original memory alerts.

The production XHTTP inbound on port 2053 uses these native stream socket options:

```json
{
  "sockopt": {
    "tcpKeepAliveIdle": 60,
    "tcpKeepAliveInterval": 20,
    "tcpUserTimeout": 60000
  }
}
```

Idle and interval are seconds; `tcpUserTimeout` is milliseconds. Set these through
native 3x-ui inbound configuration, preserving unrelated options. See the
[official socket documentation](https://xtls.github.io/config/transports/sockopt.html).
These options apply to XHTTP. Credentials, subscription URLs, ports and the other
inbound settings are unchanged. Global TCP sysctls are unchanged.

Compose sets `GODEBUG=multipathtcp=0` on 3x-ui and its child Xray process. On the
pinned runtime, the previous listener used MPTCP and did not support
`TCP_USER_TIMEOUT`; accepted TCP sockets reported zero despite the saved setting.
The 2026-10-27 container recreation switched to ordinary TCP. Kernel inspection
confirmed protocol 6, keepalive enabled, idle=60, interval=20 and user timeout=60000
on the new XHTTP listener. Configuration validation alone cannot establish that a
socket option took effect: verify both listener and accepted sockets.

The earlier `TCP_KEEPCNT=3` workaround was removed. Its isolated HTTP/1 idle-peer
test closed the dead connection after 120.83 seconds, but an HTTP/2 test with
outstanding data remained connected after five minutes. TCP keepalive alone did
not cover that retransmission case. The ordinary-TCP test results are recorded
in the [deployment review](../audit/3x-ui-candidate.md).

These timeouts reclaim unresponsive TCP peers. They do not impose an HTTP idle
timeout on clients that continue acknowledging probes. The reviewed
[XHTTP listener](https://github.com/XTLS/Xray-core/blob/v26.7.28/transport/internet/splithttp/hub.go)
does not configure `http.Server.IdleTimeout`; a durable bound on healthy idle
HTTP pools has not been established. Auto-selection checks are a hypothesis for
client activity, not proof of which device caused accumulation.

Native inbound updates can apply through the core API without restarting the
process. During the earlier hot update, the generated `config.json` remained
unchanged while the native database retained the new options. Check saved
settings and newly accepted sockets instead of treating that file as the sole
runtime authority. A normal panel/core start regenerates it from native settings;
the 2026-10-27 cold-start file contained the intended options. Do not patch only
the generated file. Already accepted connections retain their earlier options
after a hot update.

Recreation clears the existing connection population. The immediate reduction
in socket count or memory does not establish a lasting fix. Recheck counts,
goroutines and memory under real traffic; keep automatic VPN restarts disabled.
Local VPS traffic tests do not establish throughput or reliability on a particular
ISP. The 512 MiB container ceiling also does not reserve RAM on the one-GiB host:
compare host `MemAvailable` and memory pressure with container usage.

### TCP REALITY and gRPC maintenance

On 2026-11-11 the production TCP REALITY inbound on 443 received the same native
60-second idle, 20-second interval and 60,000-millisecond user timeout documented
for XHTTP above. Ordinary TCP and the effective options were verified on its
listener and an accepted socket after the authorized core restart. Inspect both
`tcp` and `tcp6` when locating sockets: a dual-stack IPv6 listener can still use
ordinary TCP protocol 6.

The previous gRPC REALITY target refused connections from the VPS. Its target
and accepted/advertised SNI now match the separately checked TCP target. Existing
gRPC clients must refresh their subscription; URLs, user credentials, REALITY
keys, short IDs and service name are preserved. Check target reachability,
TLS 1.3 and HTTP/2 before choosing a replacement; copying a once-working hostname
is not ongoing availability evidence.

All sixteen account/transport HTTPS checks, four exact XHTTP payloads and repeated
raw/JSON subscriptions passed after application. Hiddify core 5.5.5 also passed
through SSH. The owner also confirmed TCP and gRPC website access on one phone
with Hiddify 5.5.5 after refreshing the existing subscription. Fresh import, both
mobile platforms and auto-selection remain separate checks. See the
[production review and application record](../audit/production-review-2026-11-11.md).
The record includes the first application's false IPv4-only socket failure and
rollback; three core restarts occurred across both attempts.

Restarting cleared the old TCP/mux population. Keepalive reclaims unresponsive
peers; it does not impose a lifetime on responsive mux pools. Do not treat an
immediate socket/RAM decrease as a demonstrated lasting fix or schedule restarts.

### CPU alerts

The one-vCPU host has no Docker CPU quota for 3x-ui: `cpu.max` is `max 100000`,
with no configured NanoCPUs, quota or CPU pinning. The recorded check found zero
throttled periods/time. An 80% Telegram threshold is an alert setting, not a CPU
cap. The [native Linux sampler](https://github.com/MHSanaei/3x-ui/blob/v3.10.2/internal/util/sys/sys_linux.go)
reads aggregate `/proc/stat`, so its alert reflects host activity rather than
only the panel/core process. Compare it with container cgroup deltas and host
process samples. Short current samples cannot identify the process responsible
for an earlier spike. CPU settings and notification thresholds were not changed.

### Local resource history

`mirage-resources.service` samples host, process and Docker cgroup counters every
15 seconds using the Python standard library. It records the five busiest and
five largest resident processes (deduplicated), plus the panel/core even when
they are outside those lists. It records container names, CPU usage and
throttling, memory usage/limits/OOM events, host available RAM, swap activity,
major faults, CPU steal/I/O wait, scheduler counts and CPU/memory/I/O pressure.
Process I/O deltas help correlate work such as an archive or download with a spike.
Container names refresh every five minutes; unknown containers retain their ID.
Schema 2 also records per-uplink byte/packet/error/drop counters, aggregate softnet
drops/time-squeeze, core/panel FD counts and TCP state counts for production ports
443, 8443, 2053 and 9443 in the panel's network namespace. Bridges/veth/loopback
are excluded from uplink totals to avoid duplicate traffic. These counters are
not per-user accounting or proof of application throughput. Null network deltas
mean a first observation or counter reset. A PID identity change discards the
in-progress namespace measurement. Port changes require a collector review.

History stays on the VPS in `/var/log/mirage-resources/`, directory mode 0700 and
files 0600. JSONL segments rotate at 4 MiB; retention is bounded by 64 MiB and
seven-day archive age, whichever removes data sooner. Busy periods can shorten
the available history. UTC timestamps and actual interval lengths are recorded.
The collector does not read command arguments, environment variables, application
databases, packet payloads, client URLs or tokens. Socket rows are reduced to
counts; no peer addresses or client ports are retained. Do not commit diagnostic files.

There are no new Telegram messages, external uploads, scheduled analysis or VPN
restarts. Only the collector itself restarts on failure. It runs at low CPU/I/O
priority with a 64 MiB memory ceiling, independently of Compose.

Install only the collector files into the existing root-owned checkout, then:

```bash
sudo install -m 0644 /opt/mirage/infra/mirage-resources.service /etc/systemd/system/
sudo systemd-analyze verify /etc/systemd/system/mirage-resources.service
sudo systemctl daemon-reload
sudo systemctl enable --now mirage-resources.service
sudo systemctl status mirage-resources.service --no-pager
sudo tail -n 1 /var/log/mirage-resources/resources.jsonl
```

When a spike occurs, keep its time and timezone and inspect the surrounding
records, including rotated `resources-*.jsonl`. Compare process and cgroup CPU
deltas with host steal/I/O wait. For memory, distinguish a growing process from
host pressure and container `memory_events_delta.oom_kill`/`max` increments.
Resident sizes include shared pages; adding process RSS does not give unique RAM.
CPU percentages use one logical CPU as 100%; host percentages are normalized
across the host. The first interval for a newly observed PID has unknown process
CPU, not a misleading lifetime average.

Read JSONL files as a stream with a bounded summary. Loading the complete decoded
history into a list can itself consume significant RAM on this VPS. Filter local
debug endpoints to the required counters; avoid unbounded text heap exports.
The history file budget does not limit memory used by an ad hoc analysis process.

Short-lived processes can start and exit between samples. A record cannot prove
an application-level cause or assign every short spike; correlate OOM with the
kernel journal and application events around the same UTC time:

```bash
sudo journalctl -k --utc --since '1 hour ago' --grep 'oom-kill|Out of memory|Killed process'
sudo journalctl -u mirage-resources.service --since '1 hour ago'
```

To stop collection without affecting VPN, use
`sudo systemctl disable --now mirage-resources.service`. History is retained until
explicitly removed; rotation/expiry run only while the collector is active.
