# Миграция на новый VPS

Runbook описывает перенос Mirage на новый VPS при блокировке IP, замене сервера
или плановой миграции.

Не добавляй в git backup-файлы, приватные ключи, пароли, API token, DSN базы и
клиентские ссылки.

## Что подготовить

- Новый VPS с root-доступом.
- Публичный SSH-ключ `mirage_ed25519.pub`.
- Свежий backup базы 3x-ui.
- Доступ к репозиторию Mirage.
- Домен, если он уже используется для профилей или подписок.

Если домена нет, после миграции нужно выдать клиентам свежие ссылки с новым
`SERVER_HOST_OR_DOMAIN`.

## 1. Подними базовый доступ

На новом VPS:

```bash
ssh root@NEW_SERVER_IP
apt update
apt install -y ansible git
git clone --branch dev https://github.com/duckduckduck1/Mirage.git /root/mirage
cd /root/mirage/infra/ansible
ansible-playbook --syntax-check site.yml
ansible-playbook site.yml
```

Проверь вход:

```bash
ssh -i ~/.ssh/mirage_ed25519 mirage@NEW_SERVER_IP
```

После проверки включи hardening:

```bash
cd /root/mirage/infra/ansible
ansible-playbook site.yml -e enable_ssh_hardening=true --tags hardening
```

## 2. Разверни Mirage

Под пользователем `mirage`:

```bash
mkdir -p /home/mirage/projects
git clone --branch dev https://github.com/duckduckduck1/Mirage.git /home/mirage/projects/Mirage
cd /home/mirage/projects/Mirage
sudo bash ops/vpn/deploy.sh NEW_SERVER_HOST_OR_DOMAIN
```

Проверь:

```bash
sudo -E bash ops/release/check-local.sh
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops vpn-diagnose
sudo ss -tlnp | grep -E ':443|127.0.0.1:8090'
sudo ufw status numbered
```

## 3. Восстанови backup

Открой Mirage Admin через SSH-туннель:

```powershell
ssh -i $HOME\.ssh\mirage_ed25519 -N -L 8090:127.0.0.1:8090 mirage@NEW_SERVER_HOST_OR_DOMAIN
```

В Mirage Admin:

1. Импортируй backup.
2. Запусти restore.
3. Дождись успешного статуса.
4. Проверь, что `x-ui` снова active.

На VPS:

```bash
systemctl status x-ui --no-pager
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops vpn-diagnose
```

## 4. Проверь новый сервер

С локальной машины:

```powershell
Test-NetConnection NEW_SERVER_HOST_OR_DOMAIN -Port 443
```

Импортируй тестовый профиль и проверь подключение. В Mirage Admin или 3x-ui
должен расти трафик у выбранного профиля.

## 5. Переключи клиентов

Если используется домен, переключи DNS A-запись на новый IP. Держи записи в
режиме DNS only, если протокол идёт напрямую на VPS.

Если домена нет:

1. Получи свежие профили из Mirage Admin.
2. Передай новые ссылки участникам.
3. Попроси удалить старые профили из клиентских приложений.

## 6. Заверши миграцию

- Сделай новый backup на новом VPS.
- Проверь `443/tcp`, Mirage Admin и client traffic.
- Оставь старый VPS включённым до подтверждения клиентов.
- Удали старый VPS только после успешной проверки.
