# Mirage Admin

Mirage Admin — локальная панель и HTTP API для профилей, диагностики, Telegram
alerts и бэкапов. Панель слушает только `127.0.0.1:8090` и открывается через
SSH-туннель.

Основной порядок установки и работы описан в [руководстве](../../docs/guide.md).

## Запуск

```bash
sudo docker compose --env-file ops/admin/.env.local -f ops/admin/compose.yml up -d --build
```

Открыть с локальной машины:

```powershell
ssh -i $HOME\.ssh\mirage_ed25519 -N -L 8090:127.0.0.1:8090 mirage@SERVER_HOST_OR_DOMAIN
```

URL:

```text
http://127.0.0.1:8090/
```

## Env-файл

`ops/vpn/deploy.sh` создаёт `ops/admin/.env.local` автоматически. Основные
переменные:

```env
MIRAGE_ADMIN_TOKEN=PASTE_TOKEN
MIRAGE_ADMIN_BACKUP_DIR_HOST=/home/mirage/mirage-vpn/backups
MIRAGE_ADMIN_BACKUP_RETENTION_DAYS=14
MIRAGE_ADMIN_BACKUP_KEEP_MIN=3
MIRAGE_ALERTS_ENABLED=false
MIRAGE_ALERT_TELEGRAM_BOT_TOKEN=
MIRAGE_ALERT_TELEGRAM_CHAT_ID=
```

## API

Все пути `/api/v0/*` требуют заголовок:

```text
Authorization: Bearer MIRAGE_ADMIN_TOKEN
```

| Метод | Путь | Назначение |
|---|---|---|
| `GET` | `/healthz` | процесс жив |
| `GET` | `/api/v0/health` | состояние VPN, API и backup |
| `GET` | `/api/v0/access` | команды туннелей и access info |
| `GET` | `/api/v0/vpn/diagnostics` | диагностика VLESS Reality |
| `GET` | `/api/v0/profiles` | список профилей |
| `POST` | `/api/v0/profiles` | создать профиль |
| `GET` | `/api/v0/profiles/NAME` | ссылки и ручные поля профиля |
| `POST` | `/api/v0/profiles/NAME/enable` | включить профиль |
| `POST` | `/api/v0/profiles/NAME/disable` | отключить профиль |
| `GET` | `/api/v0/backups` | список backup-файлов |
| `POST` | `/api/v0/backups` | создать backup |
| `GET` | `/api/v0/backups/FILE` | скачать backup |
| `POST` | `/api/v0/backups/import` | импортировать backup |
| `POST` | `/api/v0/backups/FILE/restore` | создать restore-заявку |
| `POST` | `/api/v0/backups/prune` | удалить старые backup |
| `GET` | `/api/v0/alerts` | статус alerts |
| `POST` | `/api/v0/alerts/test` | тестовое уведомление |

Restore выполняет root-helper `mirage-admin-restore.path`: он делает
pre-restore backup, останавливает `x-ui`, заменяет базу и запускает сервис.
