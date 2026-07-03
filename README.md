# Mirage

Mirage превращает свежий VPS в управляемый VPN-сервер. Проект поднимает
Xray/3x-ui, настраивает VLESS Reality на `443/tcp`, создаёт профили доступа,
запускает локальную админ-панель и включает бэкапы.

Сервер можно заменить быстро: конфигурация, профили, бэкапы и команды
развёртывания живут в одном репозитории, а рабочие секреты остаются вне git.

## Что входит в v0.1

- безопасный bootstrap VPS через Ansible;
- установка Docker, 3x-ui/Xray и Mirage Admin одной командой;
- VLESS Reality на `443/tcp`;
- профили `main`, `partner`, `shared` и возможность создавать новые имена;
- Mirage Admin на `127.0.0.1:8090`;
- панель 3x-ui только через SSH-туннель;
- Telegram alerts;
- автоматические и ручные бэкапы базы 3x-ui;
- импорт, скачивание и восстановление бэкапа.

## Быстрый старт

Полный путь описан в [руководстве](docs/guide.md). Ниже короткая версия для уже
подготовленного VPS.

```bash
cd /home/mirage/projects/Mirage
git switch dev
git pull --ff-only origin dev
sudo bash ops/vpn/deploy.sh SERVER_HOST_OR_DOMAIN
```

В конце deploy покажет основные пути:

```text
Access file: /home/mirage/mirage-vpn/access.md
Links directory: /home/mirage/mirage-vpn/links
Backup directory: /home/mirage/mirage-vpn/backups
```

Сразу сохрани файл доступа:

```bash
sudo cat /home/mirage/mirage-vpn/access.md
```

`access.md` содержит token Mirage Admin, команды SSH-туннелей, параметры 3x-ui и
пути к профилям. Это секретный файл. Не отправляй его в чат, issue, pull request
и не добавляй в git.

## Первые настройки

### Открой Mirage Admin

На локальной машине:

```powershell
ssh -i $HOME\.ssh\mirage_ed25519 -N -L 8090:127.0.0.1:8090 mirage@SERVER_HOST_OR_DOMAIN
```

Открой в браузере:

```text
http://127.0.0.1:8090/
```

Token возьми из `/home/mirage/mirage-vpn/access.md`.

### Включи Telegram alerts

Создай бота через BotFather, открой его в Telegram и отправь боту любое
сообщение. Token не публикуй.

На VPS:

```bash
read -r -s -p "BOT_TOKEN: " TG_BOT_TOKEN; echo
TG_BOT_TOKEN="$(printf '%s' "$TG_BOT_TOKEN" | tr -d '\r\n ')"

curl -fsS "https://api.telegram.org/bot${TG_BOT_TOKEN}/getUpdates" \
  | jq -r '.result[-1].message.chat.id // empty'
```

Если команда ничего не вывела, отправь боту ещё одно сообщение и повтори её.

Открой настройки:

```bash
cd /home/mirage/projects/Mirage
sudoedit ops/admin/.env.local
```

Задай значения:

```env
MIRAGE_ALERTS_ENABLED=true
MIRAGE_ALERT_TELEGRAM_BOT_TOKEN=PASTE_BOT_TOKEN
MIRAGE_ALERT_TELEGRAM_CHAT_ID=PASTE_CHAT_ID
```

Перезапусти админку и отправь тест:

```bash
sudo docker compose --env-file ops/admin/.env.local -f ops/admin/compose.yml up -d --build

MIRAGE_ADMIN_TOKEN="$(
  sudo awk -F= '/^MIRAGE_ADMIN_TOKEN=/ {print $2; exit}' ops/admin/.env.local
)"

curl -fsS -X POST \
  -H "Authorization: Bearer $MIRAGE_ADMIN_TOKEN" \
  http://127.0.0.1:8090/api/v0/alerts/test
```

### Получи VPN-профили

Готовые профили лежат на VPS:

```text
/home/mirage/mirage-vpn/links/main.profile.txt
/home/mirage/mirage-vpn/links/partner.profile.txt
/home/mirage/mirage-vpn/links/shared.profile.txt
```

Вывести профиль заново:

```bash
cd /home/mirage/projects/Mirage
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops subscriptions --email main
```

Создать новый профиль:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops ensure-client \
  --email CLIENT_NAME \
  --print-links
```

Используй технические имена: `phone`, `tablet`, `friend-a`. Не используй ФИО,
телефоны и другие личные данные.

### Проверь бэкапы

```bash
systemctl status mirage-xui-backup.timer --no-pager
sudo /usr/local/bin/mirage-xui-backup
ls -lah /home/mirage/mirage-vpn/backups
```

Скачать конкретный файл на локальную машину:

```powershell
scp -i $HOME\.ssh\mirage_ed25519 mirage@SERVER_HOST_OR_DOMAIN:/home/mirage/mirage-vpn/backups/BACKUP_FILE.db .
```

Скачивать, импортировать и восстанавливать бэкапы удобнее через Mirage Admin.
Перед восстановлением или пересозданием VPN inbound всегда делай свежий бэкап.

## Проверка

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

Ожидаемо:

- `443/tcp` доступен снаружи;
- `8090` снаружи закрыт;
- порт панели 3x-ui снаружи закрыт;
- Mirage Admin и 3x-ui открываются только через SSH-туннель.

## Документация

- [Руководство](docs/guide.md) - установка, настройка, обслуживание и
  восстановление.
- [Архитектура](docs/architecture.md) - как устроен стек.
- [Mirage Admin](ops/admin/README.md) - технический справочник панели и API.
- [xui-ops](ops/xui/README.md) - технический справочник CLI.

## Безопасность

Не добавляй в git:

- `.env.local`, `users.local.json`, backup-файлы и дампы базы;
- `access.md`, клиентские ссылки и subscription-ссылки;
- UUID, Reality private key, short IDs;
- пароль панели, API token, `WEB_BASE_PATH`;
- реальные IP и домены, если они раскрывают рабочую инфраструктуру.

Храни секреты и бэкапы в менеджере паролей или другом защищённом хранилище.

## Структура

| Путь | Назначение |
|---|---|
| `ops/vpn` | однокомандный deploy |
| `ops/admin` | локальная админ-панель, alerts и бэкапы |
| `ops/xui` | управление 3x-ui через API |
| `infra/ansible` | первый bootstrap VPS |
| `docs` | руководство и архитектура |

## Лицензия

[MIT](LICENSE).
