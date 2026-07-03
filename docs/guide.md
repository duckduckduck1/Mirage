# Руководство Mirage

Это основной документ по Mirage v0.1. Он ведёт от свежего VPS до рабочего
VPN-сервера с админ-панелью, уведомлениями и бэкапами.

В примерах замени `SERVER_HOST_OR_DOMAIN` на IP или домен сервера. Не вставляй в
репозиторий настоящие token, пароли, ссылки VPN, UUID и backup-файлы.

## Что получится после установки

- SSH-доступ по ключу для пользователя `mirage`;
- публичный VPN-порт `443/tcp`;
- VLESS Reality inbound в 3x-ui;
- профили `main`, `partner`, `shared`;
- Mirage Admin на `127.0.0.1:8090`;
- панель 3x-ui только через SSH-туннель;
- Telegram alerts;
- ежедневные бэкапы базы 3x-ui.

## 1. Подготовь SSH-ключ

Если ключ `mirage_ed25519` уже есть, пропусти этот шаг.

PowerShell:

```powershell
ssh-keygen -t ed25519 -f $HOME\.ssh\mirage_ed25519 -C mirage
```

Linux или macOS:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/mirage_ed25519 -C mirage
```

Передай публичный ключ на VPS:

```bash
ssh root@SERVER_HOST_OR_DOMAIN "mkdir -p /root/.ssh && chmod 700 /root/.ssh"
scp ~/.ssh/mirage_ed25519.pub root@SERVER_HOST_OR_DOMAIN:/root/.ssh/mirage_ed25519.pub
```

PowerShell:

```powershell
ssh root@SERVER_HOST_OR_DOMAIN "mkdir -p /root/.ssh && chmod 700 /root/.ssh"
scp $HOME\.ssh\mirage_ed25519.pub root@SERVER_HOST_OR_DOMAIN:/root/.ssh/mirage_ed25519.pub
```

Приватный ключ не копируй на VPS.

## 2. Подготовь свежий VPS

Зайди на сервер под `root`, установи Ansible и Git:

```bash
apt update
apt install -y ansible git
```

Клонируй релизную ветку:

```bash
git clone --branch main https://github.com/duckduckduck1/Mirage.git /root/mirage
cd /root/mirage/infra/ansible
```

Запусти bootstrap:

```bash
ansible-playbook --syntax-check site.yml
ansible-playbook site.yml
```

Проверь вход с локальной машины:

```bash
ssh -i ~/.ssh/mirage_ed25519 mirage@SERVER_HOST_OR_DOMAIN
```

Когда новый вход работает, включи SSH-hardening:

```bash
cd /root/mirage/infra/ansible
ansible-playbook site.yml -e enable_ssh_hardening=true --tags hardening
```

Проверь результат:

```bash
sudo -n true
sudo ufw status
sudo /usr/sbin/sshd -T | grep -E 'passwordauthentication|kbdinteractiveauthentication|permitrootlogin|pubkeyauthentication'
```

Ожидаемо:

```text
passwordauthentication no
kbdinteractiveauthentication no
pubkeyauthentication yes
22/tcp ALLOW
443/tcp ALLOW
```

## 3. Подготовь рабочую копию

Под пользователем `mirage` клонируется отдельная рабочая копия. Root-копия из
`/root/mirage` нужна только для первого bootstrap.

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

## 4. Запусти deploy

```bash
sudo bash ops/vpn/deploy.sh SERVER_HOST_OR_DOMAIN
```

Deploy устанавливает системные пакеты, Docker, 3x-ui, Xray, Mirage Admin,
backup timer и restore helper. Также он создаёт VLESS Reality inbound и базовые
профили.

Финальный вывод содержит:

```text
Access file: /home/mirage/mirage-vpn/access.md
Links directory: /home/mirage/mirage-vpn/links
Backup directory: /home/mirage/mirage-vpn/backups
```

Сохрани `access.md` в менеджере паролей:

```bash
sudo cat /home/mirage/mirage-vpn/access.md
```

## 5. Проверь сервер

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

`PANEL_PORT` возьми из `/home/mirage/mirage-vpn/access.md`, строка
`Panel port on VPS`.

`443/tcp` должен быть доступен снаружи. `8090` и порт панели 3x-ui должны быть
закрыты снаружи.

## 6. Открой Mirage Admin

На локальной машине:

```powershell
ssh -i $HOME\.ssh\mirage_ed25519 -N -L 8090:127.0.0.1:8090 mirage@SERVER_HOST_OR_DOMAIN
```

Открой:

```text
http://127.0.0.1:8090/
```

Введи `MIRAGE_ADMIN_TOKEN` из `/home/mirage/mirage-vpn/access.md`.

## 7. Открой 3x-ui

Обычно 3x-ui нужен только для ручной проверки низкого уровня. Основные действия
делай через Mirage Admin.

На локальной машине из локальной копии репозитория:

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

## 8. Включи Telegram alerts

1. Создай бота через BotFather.
2. Открой бота в Telegram и отправь ему любое сообщение.
3. На VPS получи `chat_id`:

```bash
read -r -s -p "BOT_TOKEN: " TG_BOT_TOKEN; echo
TG_BOT_TOKEN="$(printf '%s' "$TG_BOT_TOKEN" | tr -d '\r\n ')"

curl -fsS "https://api.telegram.org/bot${TG_BOT_TOKEN}/getUpdates" \
  | jq -r '.result[-1].message.chat.id // empty'
```

4. Открой env-файл:

```bash
cd /home/mirage/projects/Mirage
sudoedit ops/admin/.env.local
```

5. Задай значения:

```env
MIRAGE_ALERTS_ENABLED=true
MIRAGE_ALERT_TELEGRAM_BOT_TOKEN=PASTE_BOT_TOKEN
MIRAGE_ALERT_TELEGRAM_CHAT_ID=PASTE_CHAT_ID
```

6. Перезапусти Mirage Admin:

```bash
sudo docker compose --env-file ops/admin/.env.local -f ops/admin/compose.yml up -d --build
```

7. Отправь тест:

```bash
MIRAGE_ADMIN_TOKEN="$(
  sudo awk -F= '/^MIRAGE_ADMIN_TOKEN=/ {print $2; exit}' ops/admin/.env.local
)"

curl -fsS -X POST \
  -H "Authorization: Bearer $MIRAGE_ADMIN_TOKEN" \
  http://127.0.0.1:8090/api/v0/alerts/test
```

## 9. Выдай VPN-профиль

Базовые профили:

| Профиль | Назначение |
|---|---|
| `main` | основной профиль |
| `partner` | отдельный близкий профиль |
| `shared` | общий профиль |

Файлы профилей:

```text
/home/mirage/mirage-vpn/links/main.profile.txt
/home/mirage/mirage-vpn/links/partner.profile.txt
/home/mirage/mirage-vpn/links/shared.profile.txt
```

Через CLI:

```bash
cd /home/mirage/projects/Mirage
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops subscriptions --email main
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops subscriptions --email main --target v2raytun
```

Создать новый профиль:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops ensure-client \
  --email CLIENT_NAME \
  --print-links
```

Удалить или отключить профиль можно в Mirage Admin.

## 10. Сделай и сохрани backup

Ручной backup:

```bash
sudo /usr/local/bin/mirage-xui-backup
ls -lah /home/mirage/mirage-vpn/backups
```

Проверить timer:

```bash
systemctl status mirage-xui-backup.timer --no-pager
```

Через Mirage Admin можно создать, скачать, импортировать, удалить и восстановить
backup.

Скачать файл на локальную машину:

```powershell
scp -i $HOME\.ssh\mirage_ed25519 mirage@SERVER_HOST_OR_DOMAIN:/home/mirage/mirage-vpn/backups/BACKUP_FILE.db .
```

Restore временно прерывает VPN. Перед restore Mirage создаёт pre-restore backup,
останавливает `x-ui`, заменяет базу и запускает сервис обратно.

## 11. Пересоздай VPN inbound

Пересоздавай inbound, если меняешь Reality target/SNI, public host, ключи Reality
или исправляешь ошибочную ручную настройку.

Перед reset:

```bash
sudo /usr/local/bin/mirage-xui-backup
```

Reset:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops bootstrap-vpn \
  --reset-inbound \
  --reality-target www.amazon.com:443 \
  --reality-sni www.amazon.com \
  --print-links
```

После reset выдай свежие ссылки и удали старые профили из клиентских приложений.

## 12. Миграция на новый VPS

1. Подними свежий VPS.
2. Выполни bootstrap.
3. Разверни Mirage через `ops/vpn/deploy.sh`.
4. Открой Mirage Admin.
5. Импортируй актуальный backup.
6. Выполни restore.
7. Проверь `443/tcp`, профили и VPN-клиенты.
8. Выдай пользователям свежие ссылки, если public host изменился.

IP считается заменяемым. Важны бэкапы, SSH-ключи и сохранённый `access.md`.

## Диагностика

### VPN-клиент показывает `unknown IP`

```bash
cd /home/mirage/projects/Mirage
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops public-host
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops vpn-diagnose
```

Если public host неверный, обнови `MIRAGE_XUI_PUBLIC_HOST` в
`ops/xui/.env.local` и пересоздай inbound.

### VPN-клиент зависает на timeout

```bash
sudo ss -tlnp | grep ':443'
sudo ufw status numbered
systemctl status x-ui --no-pager
sudo journalctl -u x-ui -n 100 --no-pager
```

Проверь, что `443/tcp` слушает Xray и открыт в `ufw`.

### Mirage Admin не открывается

```bash
cd /home/mirage/projects/Mirage
sudo docker compose --env-file ops/admin/.env.local -f ops/admin/compose.yml ps
sudo ss -tlnp | grep '127.0.0.1:8090'
curl -fsS http://127.0.0.1:8090/healthz
```

Если `8090` доступен снаружи, закрой его в firewall. Mirage Admin должен быть
доступен только через SSH-туннель.

### 3x-ui не открывается

```bash
systemctl status x-ui --no-pager
sudo /usr/local/x-ui/x-ui setting -show true
sudo ss -tlnp | grep 'ПОРТ_ПАНЕЛИ'
```

Если сервис остановлен:

```bash
sudo systemctl start x-ui
```

## Рабочие сценарии

Перед командами перейди в репозиторий:

```bash
cd /home/mirage/projects/Mirage
```

Проверить VPN:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops vpn-diagnose
sudo ss -tlnp | grep ':443'
systemctl status x-ui --no-pager
```

Посмотреть входящие в 3x-ui:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops inbounds
```

Получить профиль:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops subscriptions --email CLIENT_NAME
```

Сделать backup:

```bash
sudo /usr/local/bin/mirage-xui-backup
ls -lah /home/mirage/mirage-vpn/backups
```

Проверить firewall:

```bash
sudo ufw status numbered
```
