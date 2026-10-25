# Mirage

Docker Compose configuration and operational documentation for a personal VPN
based on [3x-ui](https://github.com/MHSanaei/3x-ui), Xray and SQLite.

## Status

**Production switched to 3x-ui on 2026-10-25.** Four users and all four transports
passed server-side HTTPS tests on their original ports; native subscriptions
passed before and after container recreation. Marzban remains stopped with its
rollback data retained. Recovery, certificate-rotation and client/observation
results are tracked in the [deployment review](audit/3x-ui-candidate.md).
The [core compatibility pin](docs/operations.md#core-compatibility) restored phone
profiles; restarting Throne restored its TCP/gRPC connections as well.

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
