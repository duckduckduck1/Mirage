# Mirage

Docker Compose configuration and operational documentation for a personal VPN
based on [3x-ui](https://github.com/MHSanaei/3x-ui), Xray and SQLite.

## Status

**Staged on the VPS; not started or operationally accepted.** The existing VPS
still runs Marzban. Separate test settings, certificates and the official image
are prepared. Available RAM prevents a concurrent test; an authorized maintenance
window is required. See the [candidate review](audit/3x-ui-candidate.md) for the
verification scope and remaining gates.

## Architecture

- Official 3x-ui and Caddy images, pinned by digest; no application fork or build.
- Four transports: VLESS TCP REALITY, gRPC REALITY, XHTTP REALITY and Trojan TLS.
- Caddy terminates HTTPS for subscriptions. Administration uses an SSH tunnel.
- The native Telegram bot provides administrative commands and alerts.
- GitHub Environment Secrets supply runtime tokens through a manual workflow.
- Host tasks provide validated certificate publication and encrypted recovery
  delivery. Persistent data and credentials remain outside the repository.

## Documentation

| Guide | Contents |
| --- | --- |
| [Setup](docs/setup.md) | Dependencies, isolated test, panel settings and inbounds |
| [Operations](docs/operations.md) | Telegram, secrets, certificates, backups and updates |
| [Recovery](docs/recovery.md) | Restore matching images, database and configuration |
| [Migration](docs/migration.md) | Existing deployment, acceptance, cutover and rollback |

After provisioning, configuration and acceptance, start the services with:

```bash
docker compose --env-file /etc/mirage/compose.env up -d
```

Images must be pulled explicitly first. This command does not install host
packages, obtain certificates, create users or migrate Marzban. The
[example environment](.env.example) uses **loopback and alternate test ports**.

## Development checks

```bash
python3 scripts/check.py
python3 -m unittest discover -s tests -v
docker compose --env-file .env.example config --quiet
git diff --check
```

The checker needs Python 3.10+ and Git. Host tasks additionally require Docker
Compose, OpenSSL and age. Encryption tests require `age` and `age-keygen`; missing
tools produce explicit skips. Local checks do not establish VPN availability.

[Changelog](CHANGELOG.md) · [License](LICENSE) ·
[Historical acceptance](audit/acceptance-ledger.md) ·
[Archived deployment](https://github.com/duckduckduck1/Mirage/tree/legacy-ansible-2026-10-23)
