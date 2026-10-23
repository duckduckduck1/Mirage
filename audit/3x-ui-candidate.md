# 3x-ui candidate review — 2026-10-24

[README](../README.md) · [Migration](../docs/migration.md)

Scope: official v3.10.2 sources, public registry metadata and local checks.
No VPS access, live subscription requests or bot messages were performed.

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
