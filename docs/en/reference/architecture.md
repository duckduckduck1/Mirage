# Architecture

Marzban provides the dashboard, SQLite, subscriptions, Telegram bot, and native
backups. Xray-core serves four inbounds, while Caddy publishes the dashboard and
subscriptions on a separate HTTPS port through Marzban's native Unix socket.

Caddy and Trojan use one DNS-01-issued certificate pair. Xray-core is pinned to
a tested version. The temporary A-13 fix is a minimal derived image until an
official upstream release includes the correction.

The user receives one URL. Server-side changes to inbounds and limits arrive
through a normal subscription refresh.
