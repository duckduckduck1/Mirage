# Mirage

Mirage превращает свежий VPS в управляемый VPN-сервер. Он устанавливает
3x-ui/Xray, поднимает VLESS Reality на `443/tcp`, создаёт VPN-профили, запускает
локальную админ-панель, включает Telegram alerts и настраивает бэкапы.

Проект рассчитан на быстрый перенос между VPS. Если IP заблокирован, ты
поднимаешь новый сервер, разворачиваешь Mirage и восстанавливаешь настройки из
бэкапа.

## Что получится

- SSH-доступ по ключу для пользователя `mirage`.
- Публичный VPN-порт `443/tcp`.
- VLESS Reality inbound в 3x-ui.
- Готовые профили `main`, `partner`, `shared`.
- Mirage Admin на `127.0.0.1:8090`.
- 3x-ui только через SSH-туннель.
- Telegram alerts.
- Автоматические и ручные бэкапы базы 3x-ui.
- Импорт, скачивание и восстановление бэкапа.

## Что нужно до начала

- VPS с Ubuntu 24.04 LTS или совместимой Ubuntu/Debian-системой.
- Root-доступ к VPS по паролю или через консоль провайдера.
- Локальный терминал: PowerShell, Windows Terminal, Linux shell или macOS
  Terminal.
- GitHub-репозиторий Mirage.
- Менеджер паролей для `access.md`, ссылок VPN, token и backup-файлов.

В командах ниже замени `SERVER_HOST_OR_DOMAIN` на IP или домен VPS. Если домена
пока нет, используй IP.

## 1. Создай SSH-ключ на локальной машине

Если ключ `mirage_ed25519` уже есть, этот шаг можно пропустить.

PowerShell:

```powershell
ssh-keygen -t ed25519 -f $HOME\.ssh\mirage_ed25519 -C mirage
```

Linux или macOS:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/mirage_ed25519 -C mirage
```

Приватный ключ не копируй на сервер и не добавляй в git.

## 2. Передай публичный ключ на VPS

На локальной машине:

```bash
ssh root@SERVER_HOST_OR_DOMAIN "mkdir -p /root/.ssh && chmod 700 /root/.ssh"
scp ~/.ssh/mirage_ed25519.pub root@SERVER_HOST_OR_DOMAIN:/root/.ssh/mirage_ed25519.pub
```

Если используешь PowerShell:

```powershell
ssh root@SERVER_HOST_OR_DOMAIN "mkdir -p /root/.ssh && chmod 700 /root/.ssh"
scp $HOME\.ssh\mirage_ed25519.pub root@SERVER_HOST_OR_DOMAIN:/root/.ssh/mirage_ed25519.pub
```

Команды могут запросить root-пароль VPS. Это нормально для первого входа.

## 3. Подготовь VPS через Ansible

Зайди на VPS под `root`:

```bash
ssh root@SERVER_HOST_OR_DOMAIN
```

Установи Ansible и Git:

```bash
apt update
apt install -y ansible git
```

Клонируй релизную ветку `main` и запусти bootstrap:

```bash
git clone --branch main https://github.com/duckduckduck1/Mirage.git /root/mirage
cd /root/mirage/infra/ansible
ansible-playbook --syntax-check site.yml
ansible-playbook site.yml
```

Bootstrap создаёт пользователя `mirage`, добавляет SSH-ключ, выдаёт sudo-доступ,
включает `ufw`, ставит `fail2ban` и оставляет парольный SSH-вход включённым до
проверки нового доступа.

## 4. Проверь вход под `mirage`

Открой новый локальный терминал и проверь вход:

PowerShell:

```powershell
ssh -i $HOME\.ssh\mirage_ed25519 mirage@SERVER_HOST_OR_DOMAIN
```

Linux или macOS:

```bash
ssh -i ~/.ssh/mirage_ed25519 mirage@SERVER_HOST_OR_DOMAIN
```

На VPS проверь sudo:

```bash
sudo -n true
```

Если команда завершилась без вывода, доступ настроен правильно.

## 5. Включи SSH-hardening

Вернись в root-сессию, где лежит `/root/mirage`, и включи hardening:

```bash
cd /root/mirage/infra/ansible
ansible-playbook site.yml -e enable_ssh_hardening=true --tags hardening
```

Проверь результат:

```bash
sudo /usr/sbin/sshd -T | grep -E 'passwordauthentication|kbdinteractiveauthentication|permitrootlogin|pubkeyauthentication'
sudo ufw status
```

Ожидаемо:

```text
passwordauthentication no
kbdinteractiveauthentication no
pubkeyauthentication yes
22/tcp ALLOW
443/tcp ALLOW
```

## 6. Клонируй проект под пользователем `mirage`

Зайди на VPS под `mirage`:

```bash
ssh -i ~/.ssh/mirage_ed25519 mirage@SERVER_HOST_OR_DOMAIN
```

PowerShell-вариант:

```powershell
ssh -i $HOME\.ssh\mirage_ed25519 mirage@SERVER_HOST_OR_DOMAIN
```

На VPS:

```bash
mkdir -p /home/mirage/projects
git clone --branch main https://github.com/duckduckduck1/Mirage.git /home/mirage/projects/Mirage
cd /home/mirage/projects/Mirage
```

Если репозиторий уже есть:

```bash
cd /home/mirage/projects/Mirage
git switch main
git pull --ff-only origin main
```

## 7. Запусти установку VPN

На VPS из `/home/mirage/projects/Mirage`:

```bash
sudo bash ops/vpn/deploy.sh SERVER_HOST_OR_DOMAIN
```

Deploy установит Docker, 3x-ui/Xray, Mirage Admin, backup timer, restore helper,
создаст VLESS Reality inbound на `443/tcp` и профили `main`, `partner`,
`shared`.

В конце появятся пути:

```text
Access file: /home/mirage/mirage-vpn/access.md
Links directory: /home/mirage/mirage-vpn/links
Backup directory: /home/mirage/mirage-vpn/backups
```

Сразу открой и сохрани файл доступа:

```bash
sudo cat /home/mirage/mirage-vpn/access.md
```

`access.md` содержит token Mirage Admin, команды SSH-туннелей, параметры 3x-ui и
пути к VPN-профилям. Это секретный файл: не отправляй его в чат, issue, pull
request и не добавляй в git.

## 8. Проверь сервер

На VPS:

```bash
sudo -E bash ops/release/check-local.sh
sudo ss -tlnp | grep -E ':443|127.0.0.1:8090'
sudo ufw status numbered
systemctl status x-ui --no-pager
```

С локальной машины:

```powershell
$Server = "SERVER_HOST_OR_DOMAIN"
$PanelPort = PANEL_PORT

Test-NetConnection $Server -Port 443
Test-NetConnection $Server -Port 8090
Test-NetConnection $Server -Port $PanelPort
```

`PANEL_PORT` возьми из `/home/mirage/mirage-vpn/access.md`.

Ожидаемо:

- `443/tcp` доступен снаружи;
- `8090` снаружи закрыт;
- порт 3x-ui снаружи закрыт;
- Mirage Admin и 3x-ui открываются только через SSH-туннель.

## 9. Открой Mirage Admin

На локальной машине:

```powershell
ssh -i $HOME\.ssh\mirage_ed25519 -N -L 8090:127.0.0.1:8090 mirage@SERVER_HOST_OR_DOMAIN
```

Открой в браузере:

```text
http://127.0.0.1:8090/
```

Token возьми из `/home/mirage/mirage-vpn/access.md`.

## 10. Включи Telegram alerts

1. В Telegram открой BotFather.
2. Создай бота и скопируй token.
3. Открой нового бота и отправь ему любое сообщение, например `test`.
4. На VPS получи `chat_id`:

```bash
read -r -s -p "BOT_TOKEN: " TG_BOT_TOKEN; echo
TG_BOT_TOKEN="$(printf '%s' "$TG_BOT_TOKEN" | tr -d '\r\n ')"

curl -fsS "https://api.telegram.org/bot${TG_BOT_TOKEN}/getUpdates" \
  | jq -r '.result[-1].message.chat.id // empty'
```

Если команда ничего не вывела, отправь боту ещё одно сообщение и повтори её.

Открой настройки Mirage Admin:

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

Перезапусти Mirage Admin:

```bash
sudo docker compose --env-file ops/admin/.env.local -f ops/admin/compose.yml up -d --build
```

Отправь тестовое уведомление:

```bash
MIRAGE_ADMIN_TOKEN="$(
  sudo awk -F= '/^MIRAGE_ADMIN_TOKEN=/ {print $2; exit}' ops/admin/.env.local
)"

curl -fsS -X POST \
  -H "Authorization: Bearer $MIRAGE_ADMIN_TOKEN" \
  http://127.0.0.1:8090/api/v0/alerts/test
```

## 11. Получи VPN-профили

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

## 12. Проверь бэкапы

```bash
systemctl status mirage-xui-backup.timer --no-pager
sudo /usr/local/bin/mirage-xui-backup
ls -lah /home/mirage/mirage-vpn/backups
```

Скачать конкретный backup на локальную машину:

```powershell
scp -i $HOME\.ssh\mirage_ed25519 mirage@SERVER_HOST_OR_DOMAIN:/home/mirage/mirage-vpn/backups/BACKUP_FILE.db .
```

Скачивать, импортировать и восстанавливать бэкапы удобнее через Mirage Admin.
Перед восстановлением или пересозданием VPN inbound всегда делай свежий backup.

## Открыть 3x-ui

Обычно 3x-ui нужен только для ручной проверки. Основные действия делай через
Mirage Admin.

Из локальной копии репозитория на Windows:

```powershell
.\ops\xui\open-panel.ps1 -ServerHost SERVER_HOST_OR_DOMAIN
```

На VPS параметры панели можно посмотреть так:

```bash
sudo /usr/local/x-ui/x-ui setting -show true
```

Если нужно сменить логин или пароль панели:

```bash
sudo /usr/local/x-ui/x-ui
```

## Обновление

На VPS под `mirage`:

```bash
cd /home/mirage/projects/Mirage
git switch main
git pull --ff-only origin main
sudo bash ops/vpn/deploy.sh SERVER_HOST_OR_DOMAIN
```

Перед обновлением сделай backup:

```bash
sudo /usr/local/bin/mirage-xui-backup
```

## Восстановление на новом VPS

1. Подними новый VPS.
2. Выполни шаги установки из этого README.
3. Открой Mirage Admin.
4. Импортируй актуальный backup.
5. Запусти restore.
6. Проверь `443/tcp` и VPN-клиенты.
7. Выдай свежие ссылки, если изменился IP или домен.

## Диагностика

Проверить VPN:

```bash
cd /home/mirage/projects/Mirage
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops vpn-diagnose
sudo ss -tlnp | grep ':443'
systemctl status x-ui --no-pager
```

Если клиент показывает `unknown IP`:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops public-host
```

Если клиент зависает на timeout:

```bash
sudo ufw status numbered
sudo journalctl -u x-ui -n 100 --no-pager
```

Если Mirage Admin не открывается:

```bash
sudo docker compose --env-file ops/admin/.env.local -f ops/admin/compose.yml ps
sudo ss -tlnp | grep '127.0.0.1:8090'
curl -fsS http://127.0.0.1:8090/healthz
```

## Документация

- [Руководство](docs/guide.md) - расширенное описание установки и обслуживания.
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

## Лицензия

[MIT](LICENSE).
