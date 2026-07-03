# Бэкапы и восстановление

Этот runbook описывает backup lifecycle Mirage v0.1: автоматический backup,
ручной backup, импорт и восстановление базы 3x-ui.

Backup-файлы, дампы базы, `x-ui.db`, client links, UUID, token, пароли и Reality
private key не добавляй в git.

## Что хранит backup

Backup базы 3x-ui содержит:

- inbound'ы;
- клиентов;
- UUID и лимиты;
- Reality-параметры;
- short IDs;
- настройки подписок 3x-ui.

Он не заменяет менеджер паролей. Отдельно храни `access.md`, пароль панели,
`WEB_BASE_PATH`, API token и SSH-ключи.

## Где лежат backup-файлы

После deploy:

```text
/home/mirage/mirage-vpn/backups
```

Проверь:

```bash
ls -lah /home/mirage/mirage-vpn/backups
```

Директория закрыта правами и не входит в git.

## Автоматический backup

Deploy устанавливает systemd timer:

```bash
systemctl status mirage-xui-backup.timer --no-pager
```

Ручной запуск той же процедуры:

```bash
sudo /usr/local/bin/mirage-xui-backup
```

Retention задаётся в `ops/admin/.env.local`:

```env
MIRAGE_ADMIN_BACKUP_RETENTION_DAYS=14
MIRAGE_ADMIN_BACKUP_KEEP_MIN=3
```

## Backup через Mirage Admin

1. Открой Mirage Admin через SSH-туннель.
2. Перейди в раздел backup.
3. Создай новый backup.
4. Скачай файл на локальную машину, если нужна внешняя копия.
5. Храни файл вне репозитория.

Через API:

```bash
MIRAGE_ADMIN_TOKEN="$(
  sudo awk -F= '/^MIRAGE_ADMIN_TOKEN=/ {print $2; exit}' ops/admin/.env.local
)"

curl -fsS -X POST -H "Authorization: Bearer $MIRAGE_ADMIN_TOKEN" \
  http://127.0.0.1:8090/api/v0/backups
```

## Проверка backup

Проверь, что backup появился в списке:

```bash
curl -fsS -H "Authorization: Bearer $MIRAGE_ADMIN_TOKEN" \
  http://127.0.0.1:8090/api/v0/backups | jq
```

Для локальной проверки SQLite:

```bash
sqlite3 /home/mirage/mirage-vpn/backups/BACKUP_FILE.db 'PRAGMA integrity_check;'
```

Ожидаемо:

```text
ok
```

## Импорт backup

Импорт через Mirage Admin сохраняет внешний SQLite backup в backup-хранилище. Он
не заменяет live-базу автоматически.

Ограничение размера задаётся в `ops/admin/.env.local`:

```env
MIRAGE_ADMIN_BACKUP_IMPORT_MAX_MB=64
```

После импорта проверь список backup-файлов и только потом запускай restore.

## Restore

Restore через Mirage Admin создаёт заявку. Root-helper:

1. повторно проверяет backup;
2. делает pre-restore backup текущей базы;
3. останавливает `x-ui`;
4. заменяет `/etc/x-ui/x-ui.db`;
5. запускает `x-ui`;
6. пишет статус заявки.

Проверить helper:

```bash
systemctl status mirage-admin-restore.path --no-pager
```

Restore временно прерывает VPN. На рабочем сервере выполняй его только в окно
обслуживания.

## Prune

Prune удаляет старые backup-файлы по retention-политике и сохраняет минимум
последних файлов.

Через API preview:

```bash
curl -fsS -X POST \
  -H "Authorization: Bearer $MIRAGE_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"dryRun": true}' \
  http://127.0.0.1:8090/api/v0/backups/prune
```

Реальное удаление требует подтверждения:

```bash
curl -fsS -X POST \
  -H "Authorization: Bearer $MIRAGE_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"dryRun": false, "confirm": "prune"}' \
  http://127.0.0.1:8090/api/v0/backups/prune
```

## Ротация после утечки

Если наружу попали ссылка, UUID, пароль панели, API token или Reality private
key:

1. Сделай backup.
2. Смени пароль панели.
3. Смени API token.
4. Пересоздай затронутый профиль или весь inbound.
5. Выдай свежие ссылки.
6. Удали старые профили из клиентских приложений.
7. Сделай новый backup.

## Чек-лист

- [ ] Backup создан до рискованного изменения.
- [ ] Backup лежит вне git.
- [ ] Внешняя копия сохранена в защищённом месте.
- [ ] Timer активен.
- [ ] Restore-helper активен.
- [ ] Restore проверен на тестовом VPS или в окно обслуживания.
