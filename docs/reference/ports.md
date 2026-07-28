# Порты

| Назначение | Порт | Протокол |
|---|---:|---|
| SSH | 22 | TCP |
| VLESS TCP REALITY Vision | 443 | TCP |
| VLESS XHTTP REALITY | 2053 | TCP |
| Панель и HTTPS-подписки Caddy | 2096 | TCP |
| VLESS gRPC REALITY | 8443 | TCP |
| Trojan TLS | 9443 | TCP |

Внутренний HTTP-порт Marzban наружу не публикуется. Перед развёртыванием
согласуйте эти порты с владельцем VPS и не освобождайте их остановкой чужих
служб.
