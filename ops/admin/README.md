# Mirage Admin

`ops/admin` — локальная панель, HTTP API и Telegram alerts для Mirage Admin.
Панель слушает `127.0.0.1`, требует `MIRAGE_ADMIN_TOKEN` для API и не
открывается в `ufw`.

## Запуск на VPS

```bash
sudo docker compose --env-file ops/admin/.env.local -f ops/admin/compose.yml up -d --build
```

Страница доступна после SSH-туннеля:

```text
http://127.0.0.1:8090/
```

Проверка:

```bash
curl -H "Authorization: Bearer $MIRAGE_ADMIN_TOKEN" \
  http://127.0.0.1:8090/api/v0/health
```

## Runtime user

Контейнеры `mirage-admin` и `mirage-alerts` запускаются без root. Compose берёт
UID/GID из `ops/admin/.env.local`:

```env
MIRAGE_ADMIN_UID=1000
MIRAGE_ADMIN_GID=1000
```

`ops/vpn/deploy.sh` заполняет эти значения автоматически по пользователю,
которому принадлежит `/home/mirage/mirage-vpn`.

При ручном запуске без `ops/vpn/deploy.sh` сначала создай host-директории и
передай их тому же UID/GID, под которым стартует контейнер:

```bash
sudo install -d -m 700 -o "$MIRAGE_ADMIN_UID" -g "$MIRAGE_ADMIN_GID" \
  /home/mirage/mirage-vpn/backups \
  /home/mirage/mirage-vpn/alerts \
  /home/mirage/mirage-vpn/restore-requests \
  /home/mirage/mirage-vpn/restore-status
```

## Telegram alerts

`mirage-alerts` запускается тем же compose-файлом. По умолчанию уведомления
выключены и сервис ничего не отправляет. Для включения задай в
`ops/admin/.env.local`:

```env
MIRAGE_ALERTS_ENABLED=true
MIRAGE_ALERT_TELEGRAM_BOT_TOKEN=PASTE_BOT_TOKEN
MIRAGE_ALERT_TELEGRAM_CHAT_ID=PASTE_CHAT_ID
```

Монитор проверяет доступность 3x-ui API, VLESS inbound, локальный порт `443`,
директорию backup, свежесть последнего backup-файла и свободное место на диске.
Уведомление отправляется только при переходе в деградацию или восстановление.
Статус alerts и тестовое уведомление доступны из локальной панели.

## Backup lifecycle

Панель умеет создавать, скачивать, удалять отдельные backup-файлы и очищать
старые backup по retention-политике. Политика задаётся в `ops/admin/.env.local`:

```env
MIRAGE_ADMIN_BACKUP_RETENTION_DAYS=14
MIRAGE_ADMIN_BACKUP_KEEP_MIN=3
MIRAGE_ADMIN_BACKUP_IMPORT_MAX_MB=64
MIRAGE_ADMIN_RESTORE_REQUEST_DIR_HOST=/home/mirage/mirage-vpn/restore-requests
MIRAGE_ADMIN_RESTORE_STATUS_DIR_HOST=/home/mirage/mirage-vpn/restore-status
```

Prune удаляет только backup-файлы старше retention-периода и всегда сохраняет
минимум `MIRAGE_ADMIN_BACKUP_KEEP_MIN` последних файлов.

Import принимает внешний SQLite backup, проверяет формат и `PRAGMA integrity_check`,
после чего сохраняет файл в backup-хранилище под новым безопасным именем.
Импорт не подменяет live-базу 3x-ui автоматически.

Restore создаёт заявку в `MIRAGE_ADMIN_RESTORE_REQUEST_DIR_HOST`. Root-helper
`mirage-admin-restore.path` забирает заявку, повторно проверяет backup, делает
pre-restore backup текущей базы, останавливает `x-ui`, заменяет `/etc/x-ui/x-ui.db`,
запускает `x-ui` и пишет статус в `MIRAGE_ADMIN_RESTORE_STATUS_DIR_HOST`.
Операция временно прерывает VPN-сервис и требует явного подтверждения имени backup.

`POST /api/v0/backups/prune` без тела или с `dryRun: true` возвращает preview.
Реальное удаление требует тело `{"dryRun": false, "confirm": "prune"}`.
Удаление одного файла требует query-параметр `confirmName`, равный имени backup.

## API v0.1

| Метод | Путь | Назначение |
|---|---|---|
| `GET` | `/healthz` | процесс admin-core жив, без секретов |
| `GET` | `/api/v0/health` | состояние 3x-ui API, inbound, порта `443`, backup-директории |
| `GET` | `/api/v0/overview` | краткий статус для главного экрана |
| `GET` | `/api/v0/access` | команды SSH-туннеля для админки и 3x-ui |
| `GET` | `/api/v0/vpn/diagnostics` | безопасная диагностика VLESS Reality |
| `GET` | `/api/v0/alerts` | безопасный статус Telegram alerts |
| `POST` | `/api/v0/alerts/test` | отправить тестовое Telegram-уведомление |
| `GET` | `/api/v0/profiles` | список профилей на VLESS inbound |
| `POST` | `/api/v0/profiles` | создать профиль по `email` |
| `GET` | `/api/v0/profiles/NAME` | ссылки и ручные поля клиента |
| `POST` | `/api/v0/profiles/NAME/enable` | включить профиль |
| `POST` | `/api/v0/profiles/NAME/disable` | отключить профиль |
| `GET` | `/api/v0/backups` | список backup-файлов |
| `POST` | `/api/v0/backups` | создать backup базы 3x-ui |
| `POST` | `/api/v0/backups/import` | импортировать внешний SQLite backup в backup-хранилище |
| `POST` | `/api/v0/backups/FILE/restore` | создать заявку на восстановление backup через root-helper |
| `POST` | `/api/v0/backups/prune` | preview или удаление старых backup по retention-политике |
| `GET` | `/api/v0/backups/FILE` | скачать backup |
| `DELETE` | `/api/v0/backups/FILE?confirmName=FILE` | удалить один backup |
| `GET` | `/api/v0/restore-requests` | список restore-заявок и статусов |
| `GET` | `/api/v0/restore-requests/JOB_ID` | статус одной restore-заявки |
