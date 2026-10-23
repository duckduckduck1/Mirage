# Mirage

Personal operating notes for a small VPN based on upstream
[Marzban](https://github.com/Gozargah/Marzban).

Marzban supplies the application, its Docker deployment, user management,
subscriptions, Telegram bot and maintenance commands. This repository documents
their use; it does not provide an installer, a separate application or a custom
Compose stack.

## Start here

| Guide | Use it for |
| --- | --- |
| [Setup](docs/setup.md) | A new, isolated installation using the official installer |
| [Operations](docs/operations.md) | Users, service status, backups and controlled updates |
| [Recovery](docs/recovery.md) | Restoring data, configuration and subscription identity |
| [Migration and troubleshooting](docs/migration.md) | Understanding the existing deployment and planning its later migration |

**Status:** the new upstream-only setup is documented, but has not passed a
separate installation, recovery or client-traffic acceptance test. Repository
checks validate documentation and guard against accidental secret additions;
they do not prove that a VPN works on a particular network.

## Existing deployment

The running deployment still uses the previous Marzban/Xray configuration and
its temporary A-13 image patch. This repository cleanup does not migrate it or
change existing users, endpoints or subscription URLs. Do not apply the new
setup instructions over that deployment.

The complete previous project, including Ansible, A-13, DNS automation and the
corrected Caddy certificate reload hook, is preserved at
[`legacy-ansible-2026-10-23`](https://github.com/duckduckduck1/Mirage/tree/legacy-ansible-2026-10-23).
Its recorded acceptance results remain in the
[acceptance ledger](audit/acceptance-ledger.md).

Documentation is maintained here in English. The former GitHub Pages site is
retired.

## Repository checks

Run with Python 3.10 or newer and Git:

```bash
python3 scripts/check.py
```

Checks cover Git-tracked files, including staged additions. They check relative
Markdown file links and common sensitive filenames and secret patterns. Keep
credentials, actual server configuration, client links and backups outside the
checkout. The heuristic guard is not a substitute for reviewing the staged diff.

See [Contributing](CONTRIBUTING.md) and the [changelog](CHANGELOG.md).
Mirage's own material is licensed under [MIT](LICENSE); upstream projects retain
their own licenses.
