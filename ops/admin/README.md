# Mirage Admin

`ops/admin` — локальная панель, HTTP API и Telegram alerts для Mirage. Панель
слушает `127.0.0.1:8090`, требует `MIRAGE_ADMIN_TOKEN` для API и не открывается
в `ufw`.

Основной путь установки: [развёртывание на VPS](../../docs/deploy.md).
Ежедневная работа: [эксплуатация](../../docs/operations.md).

## Запуск

```bash
sudo docker compose --env-file ops/admin/.env.local -f ops/admin/compose.yml up -d --build
```

Открытие через SSH-туннель:

```powershell
ssh -i $HOME\.ssh\mirage_ed25519 -N -L 8090:127.0.0.1:8090 mirage@SERVER_HOST_OR_DOMAIN
```

URL:

```text
http://127.0.0.1:8090/
```

## Runtime user

Контейнеры `mirage-admin` и `mirage-alerts` запускаются без root. UID/GID задаёт
`ops/admin/.env.local`:

```env
MIRAGE_ADMIN_UID=1000
MIRAGE_ADMIN_GID=1000
```

`ops/vpn/deploy.sh` заполняет эти значения автоматически.

## Backup lifecycle

Mirage Admin умеет:

- создавать backup базы 3x-ui;
- скачивать backup;
- импортировать внешний SQLite backup;
- создавать restore-заявку;
- удалять отдельный backup;
- очищать старые backup по retention-политике.

Retention:

```env
MIRAGE_ADMIN_BACKUP_RETENTION_DAYS=14
MIRAGE_ADMIN_BACKUP_KEEP_MIN=3
MIRAGE_ADMIN_BACKUP_IMPORT_MAX_MB=64
```

Restore выполняет root-helper `mirage-admin-restore.path`. Он делает
pre-restore backup, останавливает `x-ui`, заменяет базу и запускает сервис.

## Telegram alerts

Alerts выключены по умолчанию. Для включения:

```env
MIRAGE_ALERTS_ENABLED=true
MIRAGE_ALERT_TELEGRAM_BOT_TOKEN=PASTE_BOT_TOKEN
MIRAGE_ALERT_TELEGRAM_CHAT_ID=PASTE_CHAT_ID
```

Уведомления отправляются при деградации и восстановлении. Тестовое уведомление
доступно из панели.

## API v0.1

| Метод | Путь | Назначение |
|---|---|---|
| `GET` | `/healthz` | процесс жив, без секретов |
| `GET` | `/api/v0/health` | состояние API, inbound, порта `443`, backup |
| `GET` | `/api/v0/access` | команды SSH-туннеля и access info |
| `GET` | `/api/v0/vpn/diagnostics` | безопасная диагностика VLESS Reality |
| `GET` | `/api/v0/profiles` | список профилей |
| `POST` | `/api/v0/profiles` | создать профиль |
| `GET` | `/api/v0/profiles/NAME` | ссылки и ручные поля клиента |
| `POST` | `/api/v0/profiles/NAME/enable` | включить профиль |
| `POST` | `/api/v0/profiles/NAME/disable` | отключить профиль |
| `GET` | `/api/v0/backups` | список backup-файлов |
| `POST` | `/api/v0/backups` | создать backup |
| `POST` | `/api/v0/backups/import` | импортировать backup |
| `POST` | `/api/v0/backups/FILE/restore` | создать restore-заявку |
| `POST` | `/api/v0/backups/prune` | preview или prune |
| `GET` | `/api/v0/alerts` | статус alerts |
| `POST` | `/api/v0/alerts/test` | тестовое уведомление |
