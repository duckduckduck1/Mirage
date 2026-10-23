# Recovery

[Back to README](../README.md)

This is a recovery checklist for a new upstream installation. It has not received
a separate restoration acceptance test. Recovering the existing deployment also
requires the legacy dependencies in [Migration](migration.md).

## Recovery material

Preserve the complete SQLite state and the matching application configuration.
The quick installer normally uses `/opt/marzban` and `/var/lib/marzban`; verify
the actual database path in `.env` before taking or restoring a backup.

Include the deployment file, `.env`, Xray configuration, certificate/key files and
any non-default core or assets required by that deployment. Preserve external
DNS/ACME configuration, relevant credentials and renewal hooks separately when
the application archive does not contain them. Record exact image versions and
make any locally built rollback image recoverable outside the failed host.

Limit collection to Mirage-owned resources on a shared server. Store recovery
material encrypted outside the VPS and checkout. Keep the decryption key in a
separate protected location, and record who can recover it.

## Why a user list is insufficient

Preserving names alone does not preserve proxy credentials, inbound assignments,
Host Settings, limits, expiry, creation/revocation state or the signing secret used
to validate subscriptions. For the legacy v0.8.4 deployment, that signing secret
is stored in the database. Recreating users may invalidate old subscription URLs
even when their names match.

Restore the complete matching database rather than rebuilding accounts from a
spreadsheet or generating replacement identifiers. Retain the public URL scheme,
domain, port, subscription path and previously issued tokens when preserving
links. The endpoint must still serve a trusted certificate for its hostname.

## Inspect the archive before restoring

The [official recovery guide](https://gozargah.github.io/marzban/en/examples/backup)
describes restoring the two application directories. The current
[upstream backup script](https://github.com/Gozargah/Marzban-scripts/blob/master/marzban.sh)
also demonstrates why the producer version matters: its archive uses separate
configuration/database files and a `marzban_data` directory, and excludes the
separately installed `xray-core` directory. Do not assume all historical backups
have the same layout or include the custom core.

Inspect archive members privately and map them to the original locations before
extracting. Reject unexpected paths and link targets. Verify integrity and obtain
a consistent SQLite snapshot, including any required journal state; do not restore
an arbitrary copy of a database while another process is writing it. A working
backup must be tested with its actual producer format.

## Restoration drill

1. Prepare an isolated host and the matching upstream release. Save any existing
   destination state before replacement. Keep the test endpoint private.
2. Prevent the clone from polling the production Telegram bot, delivering backups,
   updating live DNS or issuing certificates for the production domain. Do not
   expose copied customer access to the public network.
3. Stop the destination Marzban service. Restore the matched configuration and
   database to their original paths using the inspected layout. Restore required
   external dependencies, ownership and restrictive permissions. Never extract an
   unchecked archive directly into the filesystem root.
4. Start the restored service. The upstream procedure requires an explicit
   `sudo marzban restart` after restoration; copying files does not reload them.
5. Verify database integrity, dashboard login, user states, credentials, inbound
   assignments and existing subscription tokens. Confirm a test client's traffic
   and the certificate presented by the intended HTTPS endpoint.
6. Record the tested versions, archive layout, observed results and recovery time.
   Keep production DNS and external automation unchanged throughout the drill.

Only a successful isolated drill establishes that the bundle is sufficient for
recovery. Switching a live endpoint is a separate maintenance action, with a
fresh final backup and a defined rollback point.
