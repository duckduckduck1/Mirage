# Развёртывание на VPS

Этот гайд описывает основной путь установки Mirage v0.1 на свежий VPS. В
результате ты получишь VLESS Reality на `443/tcp`, закрытые локальные панели,
профили `main`, `partner`, `shared`, бэкапы и Mirage Admin.

Не копируй в git и внешние каналы реальные IP, домены, пароли, token, UUID,
клиентские ссылки, `WEB_BASE_PATH` и backup-файлы.

## Требования

- VPS с Ubuntu 24.04 LTS или совместимой Ubuntu/Debian-системой.
- Root-доступ для первого входа.
- Локальный SSH-ключ `mirage_ed25519`.
- Доступ к репозиторию Mirage.
- Менеджер паролей для `access.md`, token, ссылок и backup-файлов.

Домен для v0.1 не обязателен. Если домена нет, используй публичный IP как
`SERVER_HOST_OR_DOMAIN`.

## 1. Bootstrap сервера

Зайди на свежий VPS под `root`, установи Ansible и Git:

```bash
apt update
apt install -y ansible git
```

Клонируй репозиторий и запусти bootstrap:

```bash
git clone --branch dev https://github.com/duckduckduck1/Mirage.git /root/mirage
cd /root/mirage/infra/ansible
ansible-playbook --syntax-check site.yml
ansible-playbook site.yml
```

Проверь новый вход с локальной машины:

```bash
ssh -i ~/.ssh/mirage_ed25519 mirage@SERVER_HOST_OR_DOMAIN
```

После успешной проверки включи SSH-hardening:

```bash
cd /root/mirage/infra/ansible
ansible-playbook site.yml -e enable_ssh_hardening=true --tags hardening
```

Проверь состояние:

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

Полная процедура описана в
[runbook Ansible-bootstrap](runbooks/bootstrap-vps-ansible.md).

## 2. Подготовь рабочую копию

Под пользователем `mirage`:

```bash
mkdir -p /home/mirage/projects
git clone --branch dev https://github.com/duckduckduck1/Mirage.git /home/mirage/projects/Mirage
cd /home/mirage/projects/Mirage
```

Если репозиторий уже есть:

```bash
cd /home/mirage/projects/Mirage
git switch dev
git pull --ff-only origin dev
```

## 3. Запусти deploy

```bash
sudo bash ops/vpn/deploy.sh SERVER_HOST_OR_DOMAIN
```

Скрипт выполняет установку и настройку:

- ставит Docker, Node.js, `jq`, `ufw` и базовые пакеты;
- закрывает старые proxy-порты и оставляет публичными `22/tcp` и `443/tcp`;
- ставит 3x-ui, если он ещё не установлен;
- привязывает 3x-ui к `127.0.0.1`;
- создаёт или использует API token 3x-ui;
- создаёт VLESS Reality inbound на `443/tcp`;
- создаёт профили `main`, `partner`, `shared`;
- поднимает Mirage Admin на `127.0.0.1:8090`;
- ставит backup timer и restore-helper;
- пишет access bundle в `/home/mirage/mirage-vpn/access.md`.

Ожидаемый финал:

```text
[HH:MM:SS] Done
Access file: /home/mirage/mirage-vpn/access.md
Links directory: /home/mirage/mirage-vpn/links
Backup directory: /home/mirage/mirage-vpn/backups
```

## 4. Проверь release gate

На VPS:

```bash
sudo -E bash ops/release/check-local.sh
```

Ожидаемо:

```text
Release gate passed
```

Если запуск без `sudo` падает на доступе к Docker socket, используй `sudo -E`.

## 5. Проверь сеть и firewall

На VPS:

```bash
PANEL_PORT="$(
  sudo sed -n 's#^MIRAGE_XUI_BASE_URL=http://127\.0\.0\.1:\([0-9][0-9]*\)/.*#\1#p' \
    ops/xui/.env.local
)"

sudo ss -tlnp | grep -E "(:443\b|127\.0\.0\.1:${PANEL_PORT}\b|127\.0\.0\.1:8090\b)"
sudo ufw status numbered
systemctl status x-ui --no-pager
```

Ожидаемо:

- `443` слушает публично;
- 3x-ui слушает `127.0.0.1:ПОРТ_ПАНЕЛИ`;
- Mirage Admin слушает `127.0.0.1:8090`;
- `ufw` открывает наружу только нужные порты, минимум `22/tcp` и `443/tcp`;
- `x-ui` active.

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

Ожидаемо: `443` доступен, `8090` и порт панели 3x-ui закрыты извне.

## 6. Открой Mirage Admin

Посмотри token и команду туннеля в access bundle:

```bash
sudo cat /home/mirage/mirage-vpn/access.md
```

Открой SSH-туннель с локальной машины:

```powershell
ssh -i $HOME\.ssh\mirage_ed25519 -N -L 8090:127.0.0.1:8090 mirage@SERVER_HOST_OR_DOMAIN
```

Открой в браузере:

```text
http://127.0.0.1:8090/
```

Введи `MIRAGE_ADMIN_TOKEN` из access bundle или из
`ops/admin/.env.local` на VPS.

## 7. Открой 3x-ui при необходимости

С Windows можно открыть 3x-ui скриптом:

```powershell
.\ops\xui\open-panel.ps1 -ServerHost SERVER_HOST_OR_DOMAIN
```

Скрипт получает данные панели через `xui-ops access-info`, открывает SSH-туннель
и запускает браузер. Окно туннеля не закрывай, пока работаешь с панелью.

## 8. Импортируй профиль

Профили лежат на VPS:

```text
/home/mirage/mirage-vpn/links/main.profile.txt
/home/mirage/mirage-vpn/links/partner.profile.txt
/home/mirage/mirage-vpn/links/shared.profile.txt
```

Для первого теста используй `main`.

1. Открой Mirage Admin или файл профиля.
2. Скопируй ссылку для Hiddify.
3. Удали старый профиль из VPN-клиента.
4. Импортируй свежую ссылку.
5. Подключись и проверь трафик.

Если клиент показывает `timeout` или `unknown IP`, открой
[эксплуатацию](operations.md#диагностика).

## 9. Сделай первый backup

Через Mirage Admin нажми создание backup или выполни на VPS:

```bash
sudo /usr/local/bin/mirage-xui-backup
```

Проверь файлы:

```bash
ls -lah /home/mirage/mirage-vpn/backups
```

Храни копию backup-файла вне репозитория.

## Итог

- [ ] SSH работает по ключу.
- [ ] `443/tcp` открыт и слушает Xray.
- [ ] 3x-ui и Mirage Admin слушают только `127.0.0.1`.
- [ ] `main`, `partner`, `shared` созданы.
- [ ] Mirage Admin открывается через SSH-туннель.
- [ ] Профиль `main` работает в Hiddify.
- [ ] Первый backup создан.

Дальше используй [эксплуатацию](operations.md).
