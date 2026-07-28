# Client compatibility

| Client | TCP REALITY | gRPC REALITY | Trojan TLS | XHTTP REALITY |
|---|---:|---:|---:|---:|
| Hiddify | Yes | Yes | Yes | No |
| Karing | Yes | Yes | Yes | No |
| V2RayTun | No | No | No | No |
| V2Box | No | No | No | No |
| Streisand | No | No | No | No |
| OneXray | No | No | No | No |
| Pinned Xray-core | Not tested | Not tested | Not tested | Yes |

“Yes” means import, VPN, changed external IP, and user traffic passed on fixed
versions. “No” does not imply a server fault: user traffic was not confirmed in
the unsupported applications even with control profiles.

An entry changes only after a new test for the exact client and OS versions:
import, connection, IP, HTTPS, Telegram/Instagram, and stable bidirectional
XHTTP traffic where applicable.
