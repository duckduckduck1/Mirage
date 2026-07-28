# Acceptance ledger

This repository record intentionally excludes infrastructure addresses, keys,
UUIDs, subscription URLs, archives, and other secrets. The complete operational
audit remains outside Git in `PLAN.md`.

## Accepted Mirage 2.0 baseline

- Marzban `v0.8.4` is used with pinned Xray-core `v24.12.31`.
- A-13 is a temporary, fail-closed one-line derivative of the official image;
  it is removed when the upstream release contains the fix.
- Four inbounds and HTTPS subscriptions passed server-side acceptance.
- Native Marzban backup delivery and a full restoration test passed. Restoration
  explicitly runs `marzban restart` after archive extraction.
- MVP user support is Hiddify and Karing for TCP REALITY, gRPC REALITY, and
  Trojan TLS. XHTTP remains server-validated only.

## Release-candidate acceptance — 2026-07-28

- The production host was rebooted. Docker, Marzban, Caddy, the panel socket,
  certificate, dynamic-DNS timer and native backup schedule recovered
  automatically.
- A fresh native backup was delivered successfully after the reboot.
- The owner confirmed the Telegram bot and supported client traffic still work.
- SSH hardening was applied through the repository role with its timed rollback.
  A separate public-key session succeeded before confirmation; effective SSH
  settings now prohibit password and root login.

## Evidence policy

Every future entry records the date, tested component versions, non-sensitive
result, and the exact acceptance criterion. Do not copy secrets or live client
links into this file.
