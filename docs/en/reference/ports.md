# Ports

| Purpose | Port | Protocol |
|---|---:|---|
| SSH | 22 | TCP |
| VLESS TCP REALITY Vision | 443 | TCP |
| VLESS XHTTP REALITY | 2053 | TCP |
| Caddy dashboard and HTTPS subscriptions | 2096 | TCP |
| VLESS gRPC REALITY | 8443 | TCP |
| Trojan TLS | 9443 | TCP |

Marzban's internal HTTP port is not public. Confirm these ports with the VPS
owner before deployment and never free them by stopping third-party services.
