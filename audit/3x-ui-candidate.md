# 3x-ui candidate review — 2026-10-24

[README](../README.md) · [Migration](../docs/migration.md)

Initial review scope: official v3.10.2 sources, public registry metadata and local
checks, without VPS access or bot messages. Subsequent authorized VPS preparation
is recorded separately below.

| Artifact | Observed value |
| --- | --- |
| 3x-ui index | `ghcr.io/mhsanaei/3x-ui:v3.10.2` |
| Index digest | `sha256:6c7e73c5bc4b6d7d70866616f78d6c9866b4904defad3077c1e2b5c1c89c2ec1` |
| Image source revision label | `608ef4e4010bf83e2e78328e08f77efc051ad4d7` |
| Checked platform | Linux amd64 |
| Extracted core | `Xray 26.10.10`, build `701af60`, Go 1.27.2 |
| Core SHA256 | `4cca4de3ab8c16b3803a70e9ebe0570d2a72480c716d89aa91603ec568bf0f44` |
| Upstream core commit | `701af60772cda123492f86e383e1fdba066614a9`, 2026-10-10 |
| Caddy candidate | `caddy:2.11.4-alpine` |
| Caddy index digest | `sha256:6aeddd44c3078b0f9a35206472a11420648a79c184603ef95957d0a20044cb2b` |

Local Docker daemon access required unavailable sudo authentication. Instead the verification
fetched the official image index, amd64 manifest and layers, verified their
SHA256 digests, extracted the core and ran **only** `version`. No proxy listener
or application container was started. The reported version matches
[DockerInit](https://github.com/MHSanaei/3x-ui/blob/v3.10.2/DockerInit.sh).

The Xray release/tag v26.10.10 returned 404, but its reported
[upstream source commit](https://github.com/XTLS/Xray-core/commit/701af60772cda123492f86e383e1fdba066614a9)
exists. This explains the binary's source reference; it is not an independent
reproducible-build verification or a reason to skip client compatibility tests.
The Caddy version is from the archived template, not a new server observation.

## Local repository checks

Sixteen tests passed with real age v1.3.2 encryption and OpenSSL fixtures:
SQLite WAL consistency, full bundle contents, contained archive paths, ciphertext
reassembly/corruption, resumable mocked delivery, bounded retention, certificate
validation/reload rollback, secret suppression and native-API request behavior.
Telegram, SSH and Docker calls were mocked; no real message was sent. Both normal
and egress-isolated Compose configurations and their exposure invariants passed
without a Docker daemon. Documentation/secret checks and Git whitespace checks
passed. These results do not replace container or server acceptance.

## Pending acceptance

Actual container startup, native API/bot delivery, all user/transport tests,
subscription cold starts, GUI/TUN, TLS continuity, downloaded recovery restoration,
48-hour observation and production cutover remain pending. The current Marzban
results do not establish these properties for the candidate.

## VPS preparation — 2026-10-24

- A fresh encrypted external recovery bundle contains the repaired Marzban core,
  a consistent SQLite snapshot with four users, both installed images, TLS/ACME,
  configuration and the four approved external maintenance scripts. Decryption,
  required members and SQLite integrity passed. Full restoration is still pending.
- Reviewed source, separate private test settings/data and a validated certificate
  copy were staged. Compose validation passed. Public bindings remain loopback.
- The official 3x-ui candidate was cached by the reviewed digest for amd64. Its
  extracted core on the VPS matched the SHA256 and version/build recorded above;
  only the binary's version command ran. The temporary unstarted inspection
  container was removed. No candidate service was started. The running Caddy reference is
  `caddy:2.11.4-alpine@sha256:5f5c8640aae01df9654968d946d8f1a56c497f1dd5c5cda4cf95ab7c14d58648`;
  the example now preserves this inventoried reference rather than the earlier
  template candidate listed above.
- All six test ports were free. Disk space was sufficient, but approximately
  304 MiB was available on an 888 MiB host, below the 512 MiB concurrent-test gate.
  The owner authorized a sequential test after preparation; memory must be
  rechecked after stopping Marzban. No stop or restart has occurred during preparation.
- A distinct SSH account/key permits only the exact staging secret receiver.
  A real authentication test reached its forced command; invalid input was rejected
  without changing settings. The private key was generated in memory and stored
  directly in GitHub, without a permanent local private-key file.
- All seven staging secret names are present. After owner Environment approval,
  the [manual delivery workflow](https://github.com/duckduckduck1/Mirage/actions/runs/40030510782)
  from merged `main` succeeded with `apply_bot=false`. On the VPS, Telegram
  confirmed the new bot token, its distinction from the legacy token, the owner's
  private chat and absence of a webhook. No message was sent or poller enabled.
- A separate consistent SQLite snapshot and private draft native API payloads
  contain all four active, unlimited, non-expiring users and all four inbounds.
  No per-user inbound exclusions were present. UUID/password, REALITY and
  transport settings were retained; only test ports and certificate paths differ.
  No tables were imported and no live database was modified. Runtime API and
  generated-subscription validation remain pending.
- Official age v1.3.2 was checked against its release asset checksum and installed.
  Its public recovery recipient was configured; the private identity was encrypted
  outside Git without plaintext persistence. A round-trip encryption test passed.
  An independent protected identity copy remains an owner task. No backup timer,
  DNS job, ACME hook or bot poller was enabled or replaced.
- Existing Marzban/Caddy container start times and restart counts remained unchanged.
  Staging files and image caching do not establish application, VPN or subscription
  acceptance.
