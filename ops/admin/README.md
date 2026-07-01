# Mirage Admin API

`ops/admin` — локальный HTTP API для будущей панели Mirage Admin. Сервис
слушает `127.0.0.1`, требует `MIRAGE_ADMIN_TOKEN` и не открывается в `ufw`.

## Запуск на VPS

```bash
sudo docker compose --env-file ops/admin/.env.local -f ops/admin/compose.yml up -d --build
```

Проверка:

```bash
curl -H "Authorization: Bearer $MIRAGE_ADMIN_TOKEN" \
  http://127.0.0.1:8090/api/v0/health
```

## API v0.1

| Метод | Путь | Назначение |
|---|---|---|
| `GET` | `/healthz` | процесс admin-core жив, без секретов |
| `GET` | `/api/v0/health` | состояние 3x-ui API, inbound, порта `443`, backup-директории |
| `GET` | `/api/v0/overview` | краткий статус для главного экрана |
| `GET` | `/api/v0/access` | команды SSH-туннеля для админки и 3x-ui |
| `GET` | `/api/v0/vpn/diagnostics` | безопасная диагностика VLESS Reality |
| `GET` | `/api/v0/profiles` | список профилей на VLESS inbound |
| `POST` | `/api/v0/profiles` | создать профиль по `email` |
| `GET` | `/api/v0/profiles/NAME` | ссылки и ручные поля клиента |
| `POST` | `/api/v0/profiles/NAME/enable` | включить профиль |
| `POST` | `/api/v0/profiles/NAME/disable` | отключить профиль |
| `GET` | `/api/v0/backups` | список backup-файлов |
| `POST` | `/api/v0/backups` | создать backup базы 3x-ui |
| `GET` | `/api/v0/backups/FILE` | скачать backup |

Restore, UI и Telegram alerts добавляются отдельными этапами.
