# About Mirage

Mirage 2.0 is infrastructure for deploying Marzban on one VPS. Marzban remains
the source of truth for users, subscriptions, the Telegram bot, and native
backups; Mirage automates only operating-system preparation and repeatable
application of the approved configuration.

Every user receives one HTTPS subscription containing VLESS TCP REALITY, VLESS
gRPC REALITY, VLESS XHTTP REALITY, and Trojan TLS.

The supported MVP minimum is Hiddify and Karing for TCP REALITY, gRPC REALITY,
and Trojan TLS. Read the [client compatibility page](/en/clients/compatibility)
before issuing access.

## Principles

- Do not add wrappers around the Marzban API.
- Do not place live infrastructure data or secrets in the repository.
- Do not automatically alter a shared VPS or third-party Docker objects.
- Treat a flow as complete only after an actual acceptance check.
