# Acceptance ledger

This repository record intentionally excludes infrastructure addresses, keys,
UUIDs, subscription URLs, archives, and other secrets. Entries below describe
dated observations of the legacy deployment, not acceptance of the new setup.
Its source is preserved at the
[legacy archive tag](https://github.com/duckduckduck1/Mirage/tree/legacy-ansible-2026-10-23).

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

## Caddy certificate reload repair — 2026-10-23

- On Caddy `2.11.4`, an unchanged Caddyfile caused a normal reload to skip
  loading the renewed certificate. The TLS reload hook now uses `--force`.
- The installed hook was backed up and updated. Caddy configuration validation
  passed, and a forced reload loaded the certificate expiring on 2026-12-25.
  The certificate presented over external HTTPS matches the renewed file.
- Existing Marzban and Caddy containers retained their identities, start times
  and restart counts. The tested stack remains Marzban `v0.8.4` with A-13 and
  Xray-core `v24.12.31`.
- Subscription URLs obtained before the change for all four active users
  returned HTTP 200 before and after it. Generic output contained four profiles;
  Hiddify and Karing output each contained three supported profiles. Connection
  parameters were unchanged in all twelve comparisons.

## Repository simplification — local checks, 2026-10-23

- The annotated tag `legacy-ansible-2026-10-23` was published to origin and
  resolves to `bf3c47e90f7b1be7898f8be14f6658ced7d0db32`.
- The active repository contains four English operating guides and one offline,
  standard-library Python checker/CI workflow. Ansible, Node/VitePress and custom
  deployment build files were removed from the active tree.
- The checker passed on the 17-file tracked tree. Eight isolated temporary Git
  fixtures passed: valid links, missing targets, untracked targets, sensitive
  filenames, an env file, a credential assignment, a public address, and safe
  placeholders. The credential failure did not echo the matched value.
- Staged whitespace, English-only content, archive identity and retired-interface
  checks passed. Ignored environments and generated documentation were preserved.
- No VPS connection, deployment command, live subscription request or bot action
  was performed for this repository change. The new upstream setup, restoration
  and client traffic remain operationally untested.

## Evidence policy

Every future entry records the date, tested component versions, non-sensitive
result, and the exact acceptance criterion. Do not copy secrets or live client
links into this file.
