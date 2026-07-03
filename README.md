# Mirage

Mirage — управляемый VPN-стек для VPS. Проект разворачивает Xray/3x-ui,
создаёт VLESS Reality на `443/tcp`, выдаёт клиентские профили и поднимает
локальную админ-панель для операций: профили, ссылки, бэкапы, восстановление и
проверка состояния.

Главная идея: сервер можно заменить быстро. IP считается расходником, а
конфигурация, профили и бэкапы остаются управляемыми.

## Что готово в v0.1

- Bootstrap свежего VPS через Ansible: пользователь `mirage`, SSH по ключу,
  `ufw`, `fail2ban`, SSH-hardening.
- Однокомандный deploy через `ops/vpn/deploy.sh`.
- 3x-ui/Xray с VLESS Reality на `443/tcp`.
- Базовые профили `main`, `partner`, `shared`.
- Mirage Admin на `127.0.0.1:8090`, без публичного доступа.
- 3x-ui панель на `127.0.0.1:ПОРТ_ПАНЕЛИ`, без публичного доступа.
- Ежедневные бэкапы базы 3x-ui, импорт и restore-helper.
- Release gate для проверки перед выпуском.

## Быстрый старт

На свежем VPS сначала выполни bootstrap из
[гайда развёртывания](docs/deploy.md), затем запусти deploy:

```bash
cd /home/mirage/projects/Mirage
git switch dev
git pull --ff-only origin dev
sudo bash ops/vpn/deploy.sh SERVER_HOST_OR_DOMAIN
```

После завершения скрипт покажет:

```text
Access file: /home/mirage/mirage-vpn/access.md
Links directory: /home/mirage/mirage-vpn/links
Backup directory: /home/mirage/mirage-vpn/backups
```

Файл `access.md` содержит локальные URL, команды SSH-туннелей, token админки и
пути к файлам профилей. Это секретный файл: не отправляй его в чат, issue, PR и
не добавляй в git.

### 1. Сохрани данные доступа

На VPS:

```bash
sudo cat /home/mirage/mirage-vpn/access.md
ls -lah /home/mirage/mirage-vpn/links
```

Сохрани содержимое `access.md` в менеджере паролей. В нём есть:

- `MIRAGE_ADMIN_TOKEN` для входа в Mirage Admin;
- команда SSH-туннеля к Mirage Admin;
- порт и `WEB_BASE_PATH` панели 3x-ui;
- пути к профилям `main`, `partner`, `shared`;
- директория backup.

### 2. Включи Telegram alerts

Создай бота через BotFather, открой его в Telegram и отправь любое сообщение
боту, например `test`. Token бота не отправляй в чат и не сохраняй в git.

На VPS безопасно введи token и найди `chat_id`:

```bash
read -r -s -p "BOT_TOKEN: " TG_BOT_TOKEN; echo
TG_BOT_TOKEN="$(printf '%s' "$TG_BOT_TOKEN" | tr -d '\r\n ')"

curl -fsS "https://api.telegram.org/bot${TG_BOT_TOKEN}/getMe"; echo
curl -fsS "https://api.telegram.org/bot${TG_BOT_TOKEN}/getUpdates" \
  | jq -r '.result[-1].message.chat.id // empty'
```

Если `getUpdates` возвращает пустой `result`, ещё раз отправь сообщение боту и
повтори команду.

Открой `ops/admin/.env.local` и задай:

```bash
cd /home/mirage/projects/Mirage
sudoedit ops/admin/.env.local
```

```env
MIRAGE_ALERTS_ENABLED=true
MIRAGE_ALERT_TELEGRAM_BOT_TOKEN=PASTE_BOT_TOKEN
MIRAGE_ALERT_TELEGRAM_CHAT_ID=PASTE_CHAT_ID
```

Перезапусти Mirage Admin и проверь тестовое уведомление:

```bash
cd /home/mirage/projects/Mirage
sudo docker compose --env-file ops/admin/.env.local -f ops/admin/compose.yml up -d --build

MIRAGE_ADMIN_TOKEN="$(
  sudo awk -F= '/^MIRAGE_ADMIN_TOKEN=/ {print $2; exit}' ops/admin/.env.local
)"

curl -fsS -X POST \
  -H "Authorization: Bearer $MIRAGE_ADMIN_TOKEN" \
  http://127.0.0.1:8090/api/v0/alerts/test
```

### 3. Открой панели

Mirage Admin открывается только через SSH-туннель. На локальной машине:

```powershell
ssh -i $HOME\.ssh\mirage_ed25519 -N -L 8090:127.0.0.1:8090 mirage@SERVER_HOST_OR_DOMAIN
```

Затем открой:

```text
http://127.0.0.1:8090/
```

Для 3x-ui используй скрипт из локальной копии репозитория:

```powershell
.\ops\xui\open-panel.ps1 -ServerHost SERVER_HOST_OR_DOMAIN
```

Логин, пароль, порт и `WEB_BASE_PATH` 3x-ui можно проверить на VPS:

```bash
sudo /usr/local/x-ui/x-ui setting -show true
sudo /usr/local/x-ui/x-ui
```

### 4. Выдай профили VPN

Готовые файлы профилей:

```text
/home/mirage/mirage-vpn/links/main.profile.txt
/home/mirage/mirage-vpn/links/partner.profile.txt
/home/mirage/mirage-vpn/links/shared.profile.txt
```

Через CLI можно вывести профиль заново:

```bash
cd /home/mirage/projects/Mirage
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops subscriptions --email main
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops subscriptions --email partner
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops subscriptions --email shared
```

Нового участника добавляй техническим именем без личных данных:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops ensure-client \
  --email friend-a \
  --print-links
```

### 5. Проверь и сохрани backup

Первый backup создаётся при deploy. Проверь timer и сделай ручной backup:

```bash
systemctl status mirage-xui-backup.timer --no-pager
sudo /usr/local/bin/mirage-xui-backup
ls -lah /home/mirage/mirage-vpn/backups
```

Скачать, импортировать, удалить или восстановить backup удобнее через Mirage
Admin в разделе бэкапов. Перед restore или reset inbound всегда делай свежий
backup.

С локальной машины можно забрать конкретный backup-файл так:

```powershell
scp -i $HOME\.ssh\mirage_ed25519 mirage@SERVER_HOST_OR_DOMAIN:/home/mirage/mirage-vpn/backups/BACKUP_FILE.db .
```

Импортировать внешний backup можно через Mirage Admin или через API:

```bash
cd /home/mirage/projects/Mirage
MIRAGE_ADMIN_TOKEN="$(
  sudo awk -F= '/^MIRAGE_ADMIN_TOKEN=/ {print $2; exit}' ops/admin/.env.local
)"

curl -fsS -X POST \
  -H "Authorization: Bearer $MIRAGE_ADMIN_TOKEN" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @BACKUP_FILE.db \
  http://127.0.0.1:8090/api/v0/backups/import
```

## Проверка после deploy

На VPS:

```bash
sudo -E bash ops/release/check-local.sh
sudo ss -tlnp | grep -E ':443|127.0.0.1:8090'
sudo ufw status numbered
```

С локальной машины:

```powershell
$Server = "SERVER_HOST_OR_DOMAIN"
$PanelPort = PANEL_PORT

Test-NetConnection $Server -Port 443
Test-NetConnection $Server -Port 8090
Test-NetConnection $Server -Port $PanelPort
```

Замени `SERVER_HOST_OR_DOMAIN` на адрес VPS, а `PANEL_PORT` — на число из
`/home/mirage/mirage-vpn/access.md` или `ops/xui/.env.local`.

Ожидаемо: `443` доступен, `8090` и порт панели 3x-ui недоступны снаружи.

## Документация

- [Развёртывание на VPS](docs/deploy.md)
- [Эксплуатация](docs/operations.md)
- [Release-check v0.1](docs/release-v0.1.md)
- [Архитектура](docs/architecture.md)
- [Bootstrap VPS через Ansible](docs/runbooks/bootstrap-vps-ansible.md)
- [Бэкапы и восстановление](docs/runbooks/backup-xui.md)
- [Миграция на новый VPS](docs/runbooks/migrate-vps.md)
- [Справочник xui-ops](ops/xui/README.md)
- [Справочник Mirage Admin](ops/admin/README.md)

## Безопасность секретов

Не добавляй в git:

- `.env.local`, `users.local.json`, backup-файлы и дампы базы;
- `access.md`, клиентские ссылки, subscription-ссылки;
- UUID, Reality private key, short IDs;
- пароль панели, API token, `WEB_BASE_PATH`;
- реальные IP и домены, если они раскрывают рабочую инфраструктуру.

Храни секреты в менеджере паролей. Директории `backups/`, `exports/`,
`secrets/`, локальные env-файлы и локальные списки пользователей уже исключены
из git.

## Состав репозитория

| Путь | Назначение |
|---|---|
| `ops/vpn` | однокомандный deploy |
| `ops/admin` | локальная админ-панель, API, alerts, backup lifecycle |
| `ops/xui` | CLI для управления 3x-ui через API |
| `infra/ansible` | первый bootstrap VPS |
| `docs` | релизная документация |

## Лицензия

[MIT](LICENSE).
