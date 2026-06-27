# Миграция на новый VPS

Runbook описывает переезд Mirage на новый сервер при блокировке IP, замене VPS
или плановом переносе инфраструктуры.

Цель миграции — сохранить клиентские subscription-ссылки и минимизировать ручные
действия на стороне клиентов.

## Что подготовить

- Новый VPS с root-доступом.
- Актуальный публичный SSH-ключ `mirage_ed25519.pub`.
- Свежий бэкап 3x-ui: база, inbound'ы, клиенты, Reality-параметры.
- Доступ к DNS-зоне домена.
- Доступ к локальному репозиторию Mirage.

Не копируй в git backup-файлы, приватные ключи, пароли, API-токены, DSN базы и
готовые клиентские ссылки.

## Перед переключением DNS

Снизь TTL записей заранее, если DNS-провайдер это позволяет:

```text
sub.ДОМЕН   TTL 60–300
vpn.ДОМЕН   TTL 60–300
```

Записи для Reality и подписок держи в режиме **DNS only**. Cloudflare proxy не
подходит как универсальная прослойка для произвольного TCP-трафика Reality.

## Подготовка нового VPS

На новом сервере выполни bootstrap:

```bash
ssh root@NEW_SERVER_IP
apt update
apt install -y ansible git
git clone --branch dev https://github.com/duckduckduck1/Mirage.git /root/mirage
cd /root/mirage/infra/ansible
ansible-playbook --syntax-check site.yml
ansible-playbook site.yml
```

Проверь вход по ключу:

```bash
ssh -i ~/.ssh/mirage_ed25519 mirage@NEW_SERVER_IP
```

Включи SSH-hardening только после проверки нового входа:

```bash
cd /root/mirage/infra/ansible
ansible-playbook site.yml -e enable_ssh_hardening=true --tags hardening
```

## Установка сервисов

Установи 3x-ui/Xray по runbook:

- [Ручная настройка 3x-ui и VLESS Reality](setup-xui-vless-reality.md)

Пока Ansible-роль для 3x-ui не готова, этот шаг выполняется вручную. После
автоматизации замени ручной шаг запуском соответствующего playbook.

## Восстановление 3x-ui

Восстанови бэкап панели через **Бэкап и восстановление** в 3x-ui или штатную
команду для выбранной базы.

Проверь:

```bash
sudo ss -tlnp | grep -E ':443|:8388|:ПОРТ_ПАНЕЛИ'
sudo ufw status
systemctl status x-ui --no-pager
```

Ожидаемые признаки:

```text
*:443                    xray-linux-amd64
127.0.0.1:ПОРТ_ПАНЕЛИ     x-ui
443/tcp ALLOW
8388/tcp ALLOW
x-ui active (running)
```

## Проверка до переключения клиентов

На локальной машине проверь доступность нового сервера:

```powershell
Test-NetConnection NEW_SERVER_IP -Port 443
Test-NetConnection NEW_SERVER_IP -Port 8388
```

Временно импортируй тестовый профиль с `NEW_SERVER_IP` и проверь:

- VLESS Reality подключается;
- Shadowsocks подключается;
- в панели растёт трафик у правильного inbound;
- панель 3x-ui не открывается напрямую снаружи.

## Переключение DNS

Когда новый VPS проверен, переключи A-записи:

```text
sub.ДОМЕН   A   NEW_SERVER_IP
vpn.ДОМЕН   A   NEW_SERVER_IP
```

Проверь резолвинг:

```bash
dig +short sub.ДОМЕН
dig +short vpn.ДОМЕН
```

На Windows можно проверить так:

```powershell
Resolve-DnsName sub.ДОМЕН
Resolve-DnsName vpn.ДОМЕН
```

## Проверка после переключения

Обнови subscription в клиентском приложении и проверь подключение.

На VPS смотри логи:

```bash
sudo journalctl -u x-ui -f
```

Если клиенты продолжают идти на старый IP, дождись истечения TTL и проверь DNS у
клиента. Если профиль содержит IP вместо домена, экспортируй профиль заново и
переходи на subscription-ссылку.

## После миграции

- Сохрани новый backup 3x-ui.
- Проверь, что старый VPS больше не обслуживает клиентов.
- Останови или удали старый VPS только после успешной проверки клиентов.
- Обнови внутренние заметки с датой миграции, провайдером и новым backup-файлом.
