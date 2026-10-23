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

## Repository publication — 2026-10-23

- The simplification was published to `origin/dev`. The
  [GitHub Actions run](https://github.com/duckduckduck1/Mirage/actions/runs/39991353216)
  for commit `d9a8aebd59fdc33327899d55cc4804a1af0f1dd1` completed successfully.
- GitHub Pages was disabled through its repository API after the new documents
  were published. A subsequent site API read returned HTTP 404.
- These are repository/hosting checks only. They do not change the legacy VPS or
  establish operational acceptance of the documented upstream setup.

## Existing-server maintenance — 2026-10-23

- Before changes, all four active users' subscriptions returned HTTP 200 in
  generic, Hiddify and Karing formats. Protocol, port, transport and REALITY short
  ID checks matched server settings. Generic output had four profiles; each
  sing-box response had three because the installed generator excludes XHTTP.
- A temporary Xray v24.12.31 client on server loopback passed an external HTTPS
  request through each of the four existing inbounds. This does not verify any
  external client network, client application or censorship-resistance claim.
- Both existing public TLS services presented trusted certificates matching the
  installed file and expiring on 2026-12-25.
- An encrypted copy was verified outside the checkout and VPS: consistent SQLite
  snapshot with four users, application configuration, ACME state, current image
  and four external maintenance scripts. Ciphertext checksum, GPG decryption and
  SQLite integrity passed. Full restoration on another VPS was not performed.
- SQLite permissions became `0600` and the data directory `0700`. The obsolete
  3x-ui backup timer was disabled; the native Marzban backup cron was preserved.
  Native backup delivery was not exercised.
- The same twelve subscription URLs returned HTTP 200 before and after the
  changes, with identical connection parameters. User/proxy credentials, signing
  state and assignments were unchanged. Marzban and Caddy container identities,
  start times and restart counts were unchanged; no working VPN service restarted.
- A failed Certbot webroot lineage with an expired, different certificate was
  observed and left unchanged pending identification of its remaining references.
- Three loose local credential files were moved into a verified encrypted archive
  outside Git; their plaintext originals were removed after byte comparison.
  Keys remain in a separate restricted local directory. Independent storage of
  those copies and password-manager storage of the keys are still owner tasks.
- This was maintenance of the existing deployment. The proposed new-install
  recipe has not gained installation, renewal or restoration acceptance.

## Existing-server core repair — 2026-10-24

- Compared all 284 tracked Python backend files with official Marzban v0.8.4 Git
  blobs: 283 matched; only `app/subscription/share.py` differed by the known A-13
  short-ID repair. This was a backend source comparison, not a full image audit.
- Reproduced modern Xray REALITY failures against the old pinned core both
  directly from the laptop and through SSH. Tested a separate localhost candidate
  with the installed Marzban API client: 20 user additions, four removals and
  system statistics succeeded without changing production users or the database.
- With explicit approval, upgraded the working pinned Xray from v24.12.31 to
  v26.7.28, added existing `publicKey` values and set REALITY `minClientVer` to
  `1.8.0`. A fresh SQLite snapshot passed integrity checks. The previous core and
  configuration were saved privately; the prepared core had already been checked
  against its official archive checksum. Marzban restarted; Caddy did not.
- All sixteen subscription requests passed before and after: four active users
  in generic, Hiddify, Karing and Xray JSON formats. Counts were respectively
  four, three, three and four per user, with identical connection parameters.
  User identity, credentials, signing state and recorded assignments were
  unchanged. The exact old URL in Throne returned an identical response body.
- All sixteen user/transport combinations passed HTTPS traffic on server
  loopback. From the laptop's physical Wi-Fi interface, both Xray v24.12.31 and
  v26.7.28 passed all four transports; official sing-box v1.13.16 passed its three
  supported profiles. XHTTP also passed a 1 MiB download and three repeated HTTPS
  requests: fifteen successful external checks in total.
- Confirmed a running new-core process in the working container. Both public TLS
  listeners retained trusted certificates matching the installed file, expiring
  on 2026-12-25. No startup traceback was observed. No rollback was needed.
- These checks did not operate the Throne GUI, establish sustained TUN stability,
  test affected Beeline/university/allowlist networks, or accept the proposed fresh
  installation. Marzban's modern-key automatic parser remains unfixed; explicit
  public keys avoid that code path for the existing configuration.

## Evidence policy

Every future entry records the date, tested component versions, non-sensitive
result, and the exact acceptance criterion. Do not copy secrets or live client
links into this file.
