# Security

- Keep secrets only in root-only files outside the Git checkout.
- Git and public documentation must never contain tokens, passwords, keys,
  certificates, live IPs, domains, UUIDs, subscription URLs, or backup archives.
- Administrators use SSH keys. Disable password login only after a second
  key-based session and the rollback mechanism have been verified.
- UFW allows only approved TCP ports. Docker is configured only on a clean VPS
  or after a separate review of the existing installation.
- The Marzban dashboard is reached through Caddy and a Unix socket, not through
  a public internal HTTP port.

If a secret may have leaked, revoke and reissue it immediately, then inspect
logs and backups. Never paste the secret into an incident report.
