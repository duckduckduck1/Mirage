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

A complete VPS outage also disables its bot. Missing daily recovery delivery is
a warning, not independent availability monitoring. Immediate host-down detection
requires an external monitor.

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
temporary API token into memory; the token is disabled afterwards. Telegram
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

`infra/backup.py` takes a consistent SQLite backup, checks integrity and encrypts
with age before delivery. Plaintext native bot backups remain disabled. The task
checks running image identities/data mounts and records the actual core version.
TLS publication is locked during its snapshot; ACME changes during archiving
invalidate the snapshot for retry.

Configure a valid age public recipient in the private host JSON. Verify initial
image/recovery delivery and downloaded restoration before enabling the timer:

```bash
sudo python3 /opt/mirage/infra/backup.py --config /etc/mirage/host.json --include-images
sudo install -m 644 infra/mirage-backup.service infra/mirage-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mirage-backup.timer
sudo systemctl list-timers mirage-backup.timer
```

Schedule: **03:00 Europe/Saratov**, persistent missed-run handling, 15-minute
failure retries. A completed daily run is not duplicated. `--include-images`
forces a pre-change bundle even on the same day. `--prepare-only` encrypts and
queues without contacting Telegram; it does not establish delivery.

Parts are at most 18 MiB with SHA256 hashes. A final manifest confirms complete
delivery. Retries skip acknowledged parts; acknowledgement-boundary failures may
produce identifiable duplicates. Pending delivery runs before new snapshots.
Image bundles are sent initially and when image IDs change; each recovery manifest
references its matching image bundle. Retain all referenced bundles in Telegram
and an independent downloaded initial set.

Only delivered daily recovery copies older than seven days are pruned locally.
Queued parts and image bundles are not automatically removed. A power loss may
leave private `.snapshot-*`, `.images-*` or `.queue-*` directories; remove only
confirmed abandoned task directories. A full disk fails the task and triggers
retry. Retire obsolete image sets only after checking retained snapshots.

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

### Memory limits

Production sets `XUI_MEMORY_LIMIT=512m`; the isolated test example retains 320m.
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
five largest resident processes (deduplicated), container names, CPU usage and
throttling, memory usage/limits/OOM events, host available RAM, swap activity,
major faults, CPU steal/I/O wait, scheduler counts and CPU/memory/I/O pressure.
Process I/O deltas help correlate work such as an archive or download with a spike.
Container names refresh every five minutes; unknown containers retain their ID.

History stays on the VPS in `/var/log/mirage-resources/`, directory mode 0700 and
files 0600. JSONL segments rotate at 4 MiB; retention is bounded by 64 MiB and
seven-day archive age, whichever removes data sooner. Busy periods can shorten
the available history. UTC timestamps and actual interval lengths are recorded.
The collector does not read command arguments, environment variables, application
databases, traffic, client URLs or tokens. Do not commit diagnostic files.

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
