# Operations

[README](../README.md) · [Setup](setup.md) · [Recovery](recovery.md) · [Migration](migration.md)

**Status: 3x-ui production switch completed on 2026-10-25.** Marzban is stopped.
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
Both targets use separate restricted SSH identities. Production delivery was
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
`/etc/mirage-test` and `/var/lib/mirage-test`.

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

Preserve the old hook for rollback. Check every certificate consumer before
changing existing output locations. The helper validates hostname, trust, expiry
and key match; publishes a versioned pair; and forces Caddy reload. Failed reload
restores the old pair and attempts recovery reload. Telegram failure notification
is attempted when configured. No VPN restart is requested. `--publish-only`
bootstraps a pair without Docker or Telegram access.

Production acme.sh installs its pair into `/var/lib/mirage/tls-source/` and calls
the helper directly with `fullchain.pem` and `key.pem`. Renewal no longer depends
on Marzban directories or its restart command. The previous domain configuration
and wrapper are retained privately for rollback.

Test Trojan's file reload against the candidate core. The previously reviewed
Xray implementation polls hourly by default: allow 65 minutes for rehearsal,
compare served leaf fingerprints on both TLS listeners and maintain an active
transfer. Files on disk alone are insufficient. This changed-certificate continuity
test remains open after the explicitly authorized production switch; publishing
the existing valid pair and checking both listeners does not establish it.
Automatic restarts are not a fallback for a failed renewal test.

## Bounded migration observation

A temporary 48-hour observation started on **2026-10-25 at 13:11 Europe/Saratov**
and ends on **2026-10-27 at 13:11 Europe/Saratov**. It does not replace the
seven-day retention period or establish access from affected Russian networks.

- Every minute: host available memory, disk space, OOM counter, container
  identity/health/restarts and server Xray PID.
- Every ten minutes: actual HTTPS through every user/transport combination and
  trusted raw/JSON subscription requests for all four users. XHTTP exact-payload
  checks run at the beginning and end.
- Check daily recovery delivery with a grace period until 04:00 Saratov; flag
  pending deliveries older than thirty minutes.
- Notify only on health changes, traffic-check failures/recovery and completion.
  A failed synthetic request can be caused by its external test endpoint and
  requires diagnosis; it does not prove an ISP block or VPN outage.
- Never restart VPN components in response to a probe failure. The observer may
  restart itself after an observer failure, preserving its original deadline and
  marking an interrupted certificate rehearsal as failed.

The bounded service is `mirage-observe-48h.service`. Its private status is
`/etc/mirage/observation-48h-status.json`; samples and helper files are under
`/var/lib/mirage-observation/`. It uses a temporary client copied from the verified
official image, with loopback-only SOCKS listeners and private configuration.
These observation helpers are not dependencies of VPN recovery or the Compose
services. The observer stops collecting and removes its client configuration
when the period finishes; retain the reports until they have been reviewed.

The workstation follow-up checks every five minutes during the certificate
rehearsal, then hourly; it reports incidents and the final result. It
requires the workstation and its local application to remain available; server
collection and Telegram notifications continue without them. A complete VPS
outage also stops its local observer and bot, so the two mechanisms have different
availability limits. After reviewing completion, disable only the temporary
observer and remove its remaining temporary files; do not change Compose.

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
then explicitly pull and recreate services in an agreed window. Never update the
core inside the container or enable unattended image updates. Repeat subscription,
traffic, TLS and recovery checks after changes.

| Symptom | Checks |
| --- | --- |
| Everyone disconnects | Restarts, OOM, disk, reboot and renewal timestamps |
| Subscriptions fail, cached profiles connect | Caddy, certificate and subscription listener |
| One client fails | Version, imported fields, routing and TUN/proxy mode |
| One network fails | Same device/profile on another network; correlated logs |

TCP connection, profile import and ping are not sufficient traffic evidence.
Several transports on one IP do not provide an independent IP fallback.
