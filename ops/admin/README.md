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
```

Prune удаляет только backup-файлы старше retention-периода и всегда сохраняет
минимум `MIRAGE_ADMIN_BACKUP_KEEP_MIN` последних файлов.

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
| `POST` | `/api/v0/backups/prune` | preview или удаление старых backup по retention-политике |
| `GET` | `/api/v0/backups/FILE` | скачать backup |
| `DELETE` | `/api/v0/backups/FILE?confirmName=FILE` | удалить один backup |

Restore добавляется отдельным этапом.
