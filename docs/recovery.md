# Recovery

[README](../README.md) · [Setup](setup.md) · [Operations](operations.md) · [Migration](migration.md)

**Status: restoration rehearsal pending.** Download and restore a complete
Telegram delivery before relying on scheduled backups or replacing Marzban.
Older encrypted Marzban recovery material remains separate.

## Required material

- Recovery delivery manifest and every corresponding encrypted part.
- The referenced image delivery manifest and encrypted image parts.
- Age private identity from its independent protected store.
- An isolated host with Docker Compose, Python, age and OpenSSL.

A user list or database alone omits deployment, certificates, renewal state and
matching binaries. GitHub Secrets are not a downloadable recovery archive and do
not replace the age identity. Neither the VPS nor Telegram stores that identity.

## Verify and decrypt

Download from the private administrator bot conversation. Identify parts by bundle
ID/number, not Telegram's renamed local filenames. In a new mode 0700 directory
outside Git, compare every part against its manifest:

```bash
umask 077
sha256sum part-*.age.part
cat part-*.age.part > bundle.age
age --decrypt -i /PRIVATE_KEY_STORE/identity -o recovered.bin bundle.age
```

Reject missing/extra parts and incorrect hashes. Assemble in numeric order and
keep image/recovery bundles separate. Age authentication must succeed. The image
payload is a Docker-save tar; recovery is gzip-compressed tar. Do not print,
commit or upload plaintext. Remove temporary decrypted data after the rehearsal.

## Restore in isolation

1. Inspect recovery members and link targets. Reject absolute paths, escaping
   `..`, devices and links outside staging. Extract into private staging, not `/`.
2. Read the inner `manifest.json`: exact image IDs/digests, actual core, SQLite
   checksum and referenced image-bundle ID. Verify SQLite integrity and checksum.
3. Load the verified Docker-save tar. Docker save/load does not reliably restore
   registry digest associations. For offline recovery, tag the loaded images as
   `mirage-recovery/x-ui:IMAGE_ID_HEX` and `mirage-recovery/caddy:IMAGE_ID_HEX`, using
   each complete 64-character configuration ID from the inner manifest. Verify
   `docker image inspect` matches those IDs before starting. These are the saved
   official images, not rebuilt images.
4. Restore `deployment/compose.yaml` and `deployment/infra/` to `/opt/mirage`;
   private settings to `/etc/mirage`; `state/db` and `state/tls` to `/var/lib/mirage`.
   Use root ownership, directories 0700 and private files 0600. Set image variables
   to the verified recovery tags. Host helpers validate these tags against actual
   immutable image IDs. `pull_policy: never` prevents registry substitution.
5. For a rehearsal, use separate test project/data paths, test ports and matching
   host JSON. Start with `-f compose.yaml -f infra/restore-isolated.yaml`: its
   internal Docker network must block Internet egress before the copied bot can
   poll. Verify that restriction, then disable Telegram in the native panel over
   the SSH tunnel. Only then recreate on the normal test network for traffic
   checks. Do not run delivery, backup, ACME, DNS or restored cron jobs in the clone.
6. Verify administrator access, users, UUID/passwords, state, expiry, remaining
   quotas, four assignments, existing 3x-ui subscriptions and actual traffic.
   Repeat cold-start and XHTTP payload checks. Record elapsed recovery time.
7. For actual recovery, restore ACME at the recorded private location and merge
   only the saved ACME cron entry. Do not overwrite unrelated root jobs. Check
   DNS credentials and certificate reload consumers before enabling renewal.
   Reestablish GitHub token delivery and enable backup scheduling only on the
   intended production instance.

During offline restore, keep verified local image-ID tags. Once registry access
returns, explicitly pull the recorded official digest, verify the image identity
and update the environment deliberately. Never substitute `latest` or run an
older image against a migrated database without its matching snapshot.

Restoring the database preserves 3x-ui subscription IDs when public host/port/paths
remain unchanged. It does not recreate Marzban signing-token semantics. The
proposed ten-minute rollback target requires measurement, not assumption.

## Recovery archive contents

The bundle includes a consistent SQLite snapshot, additional database-directory
state, TLS releases, ACME account/configuration, Compose/private host settings,
host tasks, the relevant ACME cron entry, image identity metadata and this guide.
Image payloads are delivered separately and linked by bundle ID. Keep every image
bundle referenced by retained recovery snapshots.

Historical encrypted files under `~/.local/share/mirage/` remain recovery material,
not the new runtime token source. Retain an independent archive copy and its key
separately. Marzban rollback still requires its A-13 image, core, signing state,
configuration and external scripts; see [Migration](migration.md#migration-to-3x-ui).
