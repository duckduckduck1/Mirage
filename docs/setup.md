# Setup

[README](../README.md) · [Operations](operations.md) · [Recovery](recovery.md) · [Migration](migration.md)

**Status: production switched on 2026-10-25.** The procedure below retains safe
alternate-port defaults for a separate installation or rehearsal. Preserve the
working deployment until a replacement has passed its own checks.

The previous staging installation was removed on 2026-10-26. These test paths
describe a future isolated rehearsal, not an existing server installation.

## Requirements and versions

- Linux host with Docker Engine and Compose v2+, Python 3.10+, OpenSSL and age.
  Generate the private recovery identity with age-keygen on a trusted workstation.
- Administrative SSH access, a valid DNS hostname and its existing trusted certificate.
- A measured memory budget, free test ports and disk space for image archives.
- A current recovery copy of the existing production deployment before changing it.

The [example environment](../.env.example) pins official 3x-ui v3.10.2 and the
existing Caddy version/digest observed on 2026-10-24. Recheck the running image
identities before a later deployment; do not substitute a moving tag.

The upstream [Compose file](https://github.com/MHSanaei/3x-ui/blob/v3.10.2/docker-compose.yml)
builds the application locally. This repository instead consumes its official
image. Its bundled amd64 core is Xray 26.10.10, subsequently withdrawn upstream.
Do not treat this image/core combination as an accepted fresh installation.
Production uses an official core selected through native 3x-ui Core Management
and persisted separately; see [core compatibility](operations.md#core-compatibility).
Validate the actual core and clients before public exposure. The
[candidate review](../audit/3x-ui-candidate.md) records the limitations.

## Test isolation

| Connection | Test port | Production port |
| --- | --- | --- |
| VLESS TCP REALITY | 24443 | 443 |
| VLESS gRPC REALITY | 28443 | 8443 |
| VLESS XHTTP REALITY | 22053 | 2053 |
| Trojan TCP TLS | 29443 | 9443 |
| Caddy HTTPS subscriptions | 22096 | 2096 |
| Administrative panel, loopback | 12080 | 12080 |

Use a separate Compose project, bridge network and data directories. Never share
production SQLite or writable Marzban directories. The two services are capped
at 320 and 64 MiB in the example, with no additional swap budget. Production uses
`XUI_MEMORY_LIMIT=512m` after a confirmed container-limit OOM; its original 320 MiB
test cap was insufficient under real use. Stop the test on memory pressure,
OOM or degradation of the existing VPN. An occupied test port blocks preparation.

The 888 MiB VPS did not meet the original conservative 512 MiB startup gate.
After measurement, the owner approved a sequential runtime test with the same
container caps and immediate rollback below 128 MiB available memory, on OOM or
unexpected container failure. That test passed; an upgrade was not required for
the measured workload. Limits are ceilings, not preallocated RAM. This result
does not establish capacity for more users, high concurrency or simultaneous
recovery clones. Keep the 512 MiB budget for concurrent testing unless separately
reviewed. Never stop unrelated workloads to meet it implicitly.

Place the checkout at `/opt/mirage`. Create root-owned mode 0700 directories
`/etc/mirage-test`, `/var/lib/mirage-test`, and its `db` and `tls` subdirectories.
Copy `.env.example` to `/etc/mirage-test/compose.env`, mode 0600, and configure the
real hostname. Use literal, unquoted KEY=value entries for the host helpers.

Copy `infra/host.example.json` to `/etc/mirage-test/host.json`, mode 0600. Set
`env_file=/etc/mirage-test/compose.env` and `state_dir=/var/lib/mirage-test`; its
hostname must match the Compose environment. Do not enable test ACME/DNS jobs.
Configure `acme_dir` only for a deliberate recovery drill with copied state and
disabled renewal schedules. Runtime tokens are delivered from GitHub as described
in [Operations](operations.md#secret-management).

The default `BIND_IP=127.0.0.1` prevents public access during preparation. After
credentials and inbounds are checked, change it to the public IPv4 listener and
allow only the test TCP ports in both host and provider firewalls. Check Docker's
actual published-port rules; a host firewall frontend alone may not block them.
IPv6 remains unpublished until separately configured and tested.

## Bootstrap and first login

Copy the working certificate pair to private staging without changing its existing
consumers. The helper requires a matching hostname/key, trusted chain and at least
seven days of remaining validity. Bootstrap the managed certificate directory:

```bash
sudo python3 /opt/mirage/infra/tls.py --config /etc/mirage-test/host.json \
  --certificate /PRIVATE_STAGING/fullchain.pem --key /PRIVATE_STAGING/key.pem --publish-only
sudo docker compose --env-file /etc/mirage-test/compose.env pull --policy always
sudo docker compose --env-file /etc/mirage-test/compose.env up -d x-ui
sudo docker compose --env-file /etc/mirage-test/compose.env exec -T x-ui /app/x-ui -v
sudo docker compose --env-file /etc/mirage-test/compose.env exec -T x-ui /app/bin/xray-linux-amd64 version
```

The core path is for amd64; verify the image architecture first. No archived
installer or host bootstrap is required. Images use `pull_policy: never` during
normal startup so pulls and version changes remain deliberate.

Open an administration tunnel from the workstation:

```bash
ssh -N -L 12080:127.0.0.1:12080 ADMIN_USER@SERVER_HOST
```

Open `http://127.0.0.1:12080/`, replace default credentials immediately and enable
TOTP. Keep panel base path `/` for the reviewed secret-delivery helper. The panel
is published only on host loopback and is not routed through Caddy.
Run native initialization commands sequentially. Do not run another CLI database
migration while the first server startup is initializing an empty SQLite database.

## Panel configuration

Configure the native panel before public exposure:

| Setting | Value |
| --- | --- |
| Panel port | 12080; also forced by `XUI_PORT` |
| Panel listener | All container interfaces; host publication remains loopback |
| Subscription enabled | Yes |
| Subscription listener / port | All container interfaces / 12081 |
| Raw / Xray JSON paths | `/sub/` / `/json/` |
| Native subscription TLS | Disabled; Caddy terminates HTTPS |
| Public subscription URI | Actual HTTPS hostname and current test port |
| Advertised proxy addresses | Actual public host/IP, never a container address |
| Fail2ban / IP limits | Disabled |
| Built-in plaintext bot backup | Disabled |

The [subscription listener](https://docs.sanaei.dev/docs/config/subscription/) is
separate from the panel. Verify generated addresses and ports; do not assume
forwarded headers choose the correct public endpoint. Caddy exposes `/sub/*` and
`/json/*`; other paths, including panel/API routes, return 404. Its admin endpoint
is container-local and unpublished.

## Inbounds and users

Recreate the four existing inbounds through native 3x-ui tools. Preserve protocol,
security, REALITY keys/SID/SNI/client-version bounds, flow, gRPC service name,
XHTTP path/mode, TLS and required routing behavior. Set actual inbound ports to
the test ports: Compose maps each port to itself. Retain 3x-ui's own API/statistics
plumbing; do not replace its complete core configuration with Marzban's output.
Resolve Marzban's server-IP placeholder to the actual advertised endpoint. Its
unspecified fingerprint sentinel `none` is invalid in generated Xray REALITY
settings; the accepted deployment uses explicit `chrome`. Verify raw and JSON
output, rather than copying those values verbatim between panels.

Trojan reads `/certs/current/fullchain.pem` and `/certs/current/key.pem` from the
read-only parent mount. Set `oneTimeLoading=false` and test certificate
reloading with the actual candidate core before claiming uninterrupted renewal.

Create one client per person, attach four inbounds and preserve UUID, Trojan
password, status, expiry and remaining quota. Unlimited remains unlimited.
Never encode an exhausted finite allowance as zero/unlimited: keep the client
disabled with its finite limit recorded until more traffic is deliberately granted.
Historical usage remains in the legacy archive. Do not import Marzban SQL tables
or signing tokens. Leave friends' Telegram IDs unlinked for admin-only operation.

Start the configured services:

```bash
sudo docker compose --env-file /etc/mirage-test/compose.env up -d
```

Complete the [acceptance matrix](migration.md#migration-to-3x-ui), including
client traffic, cold starts, TLS and recovery. Do not enable timers or distribute
candidate subscriptions before their corresponding checks pass.
