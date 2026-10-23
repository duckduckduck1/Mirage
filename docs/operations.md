# Operations

[Back to README](../README.md)

These notes use the
[official Marzban command](https://gozargah.github.io/marzban/en/docs/marzban-script).
Check `sudo marzban help` for the installed script's interface. Run server
commands only as a deliberate operating action; repository checks never run them.

## Users and service state

Use the dashboard, optional upstream Telegram bot or official CLI to create,
disable and remove users, assign inbounds, and set limits and expiry dates.
Give each person their own subscription. A subscription URL grants access and
must be treated as a credential.

Useful commands on the intended host:

```bash
sudo marzban status
sudo marzban logs
```

Logs can contain credentials or subscription request paths. Inspect locally and
redact them before sharing. An application being up does not demonstrate usable
VPN traffic from a client network.

`sudo marzban restart` applies changed application settings and interrupts the
service. `sudo marzban edit-env` opens configuration; it is not a status command.
Preserve working access while making changes on a shared VPS.

## Backups

Use the upstream backup interface, configured interactively on the host:

```bash
sudo marzban backup-service
sudo marzban backup
```

The first command configures delivery and scheduling; the second requests a
manual backup. Either can send data through the configured delivery channel.
Do not execute them from CI or a test clone with production bot credentials.

Confirm delivery, archive readability and a restoration test. A scheduled cron
entry alone does not establish that any usable backup exists. Keep a protected,
encrypted recovery copy outside the VPS, with the decryption key stored
separately; delivery through Telegram does not replace this copy.

Include configuration and external dependencies as described in
[Recovery](recovery.md). Verify SQLite consistency for the installed producer;
copying an actively written database file is not a guaranteed consistent backup.
When consistency cannot be established, take an offline copy during a planned
service stop. Do not add a second custom backup service around Marzban.

## Updates and rollback

1. Record the current image tag and digest, installed management-script version,
   Xray version and local overrides. Keep the exact rollback image accessible.
2. Obtain a fresh external backup and review upstream release notes. Rehearse on
   an isolated copy with delivery, DNS changes and production bot polling disabled.
3. Use the upstream update procedure only after choosing the intended release and
   maintenance window. The documented `sudo marzban update` follows the upstream
   updater; it is not a promise to preserve a locally patched image or core.
4. Recheck subscriptions, profile parameters, actual client traffic and the served
   certificate. Record the resulting versions and observed results.
5. If the update fails, return to the recorded image and configuration. If a
   database migration occurred, restore the matching pre-update data as well.

Do not apply this updater blindly to the existing A-13 deployment. Its transition
is a separate [migration](migration.md). Do not treat an image rollback as a
database downgrade, or run old and new application instances against one database.

Avoid unattended application or core upgrades. `sudo marzban core-update` is an
upstream option for intentionally selecting another Xray build; it is not a
required extra step for a fresh install. Test server/client compatibility before
using a different core.

## Routine checks

- Check the public HTTPS endpoint and the expiry of the certificate it actually
  presents. Check again after renewal.
- Verify backup delivery and repeat an isolated restoration drill when the backup
  format, producer or procedure changes.
- Keep enough disk space for data and logs, and inspect unexpected restarts.
- Restrict configuration, SQLite data and recovery material to the required
  accounts; inspect directory traversal permissions as well as file modes.
- For network-specific failures, follow [Troubleshooting](migration.md#troubleshooting).

The [ledger](../audit/acceptance-ledger.md) contains historical evidence. Its old
results do not establish acceptance for newly installed versions or networks.
