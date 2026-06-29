# Установка VPN на VPS

Этот гайд описывает развёртывание Mirage VPN на свежем VPS. В результате ты
получишь защищённый сервер, панель 3x-ui за SSH-туннелем, VLESS Reality на
`443/tcp` и готовые профили `main`, `partner`, `shared`.

Команды выполняются на VPS под пользователем `mirage`, если явно не указано
иначе. Реальные IP, домены, пароли, API token, UUID, `vless://`-ссылки и backup
файлы не добавляй в git и не отправляй во внешние каналы.

## Целевая схема

```text
Клиент Hiddify
  └─ VLESS Reality: SERVER_HOST_OR_DOMAIN:443

VPS
  ├─ 22/tcp                 SSH по ключу
  ├─ 443/tcp                Xray VLESS Reality
  └─ 127.0.0.1:ПОРТ_ПАНЕЛИ  3x-ui через SSH-туннель
```

Порт панели 3x-ui не открывается наружу. Для входа в кабинет используется
локальный SSH-туннель.

## Что подготовить

- VPS с Ubuntu 24.04 LTS или совместимой Ubuntu/Debian-системой.
- Root-доступ для первого входа.
- Локальный SSH-ключ `mirage_ed25519`.
- Репозиторий Mirage на ветке `dev`.
- Менеджер паролей для логина панели, пароля, `WEB_BASE_PATH`, API token,
  клиентских ссылок и backup-файлов.

Домен не обязателен для первого запуска. Он понадобится позже для стабильных
адресов и подписок при переезде на новый VPS.

## Шаг 1. Bootstrap VPS

На свежем VPS зайди под `root`, установи Ansible и Git, затем запусти bootstrap
из репозитория.

```bash
apt update
apt install -y ansible git
git clone --branch dev https://github.com/duckduckduck1/Mirage.git /root/mirage
cd /root/mirage/infra/ansible
ansible-playbook --syntax-check site.yml
ansible-playbook site.yml
```

Проверь новый вход с локальной машины:

```bash
ssh -i ~/.ssh/mirage_ed25519 mirage@SERVER_IP
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

Ожидаемые признаки:

```text
passwordauthentication no
kbdinteractiveauthentication no
pubkeyauthentication yes
22/tcp ALLOW
443/tcp ALLOW
```

Полная процедура описана в
[runbook Ansible-bootstrap](../runbooks/bootstrap-vps-ansible.md).

## Шаг 2. Подготовка рабочей папки

После bootstrap работай под пользователем `mirage`.

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

## Шаг 3. Установка 3x-ui

Скачай и запусти установщик:

```bash
curl -Ls https://raw.githubusercontent.com/MHSanaei/3x-ui/master/install.sh -o /tmp/3x-ui-install.sh
sudo bash /tmp/3x-ui-install.sh
```

Выбери параметры:

| Вопрос установщика | Значение |
|---|---|
| **Database Selection** | `SQLite` |
| **Panel Port** | случайный высокий порт `10000–60000`, не `22` и не `443` |
| **Username / Password** | сильные значения, не `admin/admin` |
| **WebBasePath** | случайный секретный путь |
| **SSL Certificate Setup** | **Skip SSL** |
| **Bind the panel to 127.0.0.1 only?** | `y` |

Почему SSL панели можно пропустить: кабинет работает по HTTP только внутри
SSH-туннеля. Наружу порт панели не открыт.

Если панель после установки остановлена, запусти её:

```bash
sudo systemctl start x-ui
sudo systemctl enable x-ui
```

Проверь bind панели:

```bash
sudo ss -tlnp | grep 'ПОРТ_ПАНЕЛИ'
```

Ожидаемо:

```text
127.0.0.1:ПОРТ_ПАНЕЛИ
```

Если панель слушает не `127.0.0.1`, исправь:

```bash
sudo /usr/local/x-ui/x-ui setting -listenIP 127.0.0.1
sudo systemctl restart x-ui
```

## Шаг 4. Где смотреть данные панели

Установщик 3x-ui сохраняет результат в root-only файле:

```bash
sudo cat /etc/x-ui/install-result.env
```

В нём могут быть:

```text
XUI_USERNAME=...
XUI_PASSWORD=...
XUI_ACCESS_URL=...
```

Не копируй этот вывод в чат, issue, PR или документацию.

Посмотреть порт и `WEB_BASE_PATH` можно так:

```bash
sudo /usr/local/x-ui/x-ui setting -show true
```

Команда может не показывать логин и пароль, если дефолтные данные уже заменены.
Если пароль потерян, открой меню:

```bash
sudo /usr/local/x-ui/x-ui
```

В меню выбери пункт изменения логина или пароля панели. После смены обнови
локальные секреты и `ops/xui/.env.local`.

## Шаг 5. Установка Docker

Установи Docker удобным для текущей ОС способом. После установки проверь:

```bash
docker --version
sudo docker compose version
```

Команды `xui-ops` ниже запускаются через `sudo docker compose`, чтобы контейнер
мог использовать host network и видеть панель на `127.0.0.1`.

## Шаг 6. Настройка xui-ops

Создай локальный env-файл на VPS:

```bash
cd /home/mirage/projects/Mirage
cp ops/xui/.env.example ops/xui/.env.local
nano ops/xui/.env.local
```

Заполни значения:

```text
MIRAGE_XUI_BASE_URL=http://127.0.0.1:ПОРТ_ПАНЕЛИ/WEB_BASE_PATH
MIRAGE_XUI_PUBLIC_HOST=SERVER_HOST_OR_DOMAIN
MIRAGE_XUI_API_TOKEN=
MIRAGE_XUI_TUNNEL_LOCAL_PORT=2096
MIRAGE_SSH_HOST=SERVER_HOST_OR_DOMAIN
MIRAGE_SSH_USER=mirage
MIRAGE_SSH_KEY=$HOME\.ssh\mirage_ed25519
MIRAGE_XUI_VLESS_PORT=443
MIRAGE_XUI_VLESS_REMARK=vless-reality-vision
MIRAGE_XUI_REALITY_TARGET=www.amazon.com:443
MIRAGE_XUI_REALITY_SNI=www.amazon.com
```

Если домена пока нет, в `MIRAGE_XUI_PUBLIC_HOST` укажи публичный IP сервера.
После покупки домена замени значение на `vpn.ДОМЕН` и пересоздай ссылки.

Если API token ещё не создан, временно добавь в `.env.local` логин и пароль
панели. Строку `MIRAGE_XUI_API_TOKEN` на это время очисти или закомментируй,
иначе CLI попробует использовать placeholder как Bearer token.

```text
# MIRAGE_XUI_API_TOKEN=
MIRAGE_XUI_USERNAME=...
MIRAGE_XUI_PASSWORD=...
```

Создай token:

```bash
sudo docker compose -f ops/xui/compose.yml build
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops create-token --name mirage-ops
```

Сохрани token в менеджере паролей, укажи его в `MIRAGE_XUI_API_TOKEN`, затем
удали `MIRAGE_XUI_USERNAME` и `MIRAGE_XUI_PASSWORD` из `.env.local`.

Проверь доступ к API:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops inbounds
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops access-info
```

## Шаг 7. Выбор Reality target и SNI

Reality использует внешний TLS-сайт как маскировку. В клиентской ссылке будут
target, SNI, публичный ключ и short ID. Для корректной работы домен target и SNI
должны совпадать.

Рекомендуемый вариант для текущей схемы:

```text
target: www.amazon.com:443
SNI:    www.amazon.com
```

Почему так:

- домен стабильно обслуживает TLS на `443/tcp`;
- профиль выглядит как обычный HTTPS-трафик к крупному публичному сервису;
- текущая конфигурация проверена на нескольких устройствах.

Резервный кандидат:

```text
target: www.microsoft.com:443
SNI:    www.microsoft.com
```

Reality target помогает против протокольной фильтрации и активного зондирования,
но не защищает сам IP сервера. Если оператор блокирует IP VPS, нужен новый VPS,
бэкап и миграция.

## Шаг 8. Создание VPN inbound и профилей

Основная команда создаёт или пересоздаёт VLESS Reality inbound на `443/tcp`,
создаёт профили `main`, `partner`, `shared` и выводит ссылки.

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops bootstrap-vpn \
  --reset-inbound \
  --reality-target www.amazon.com:443 \
  --reality-sni www.amazon.com \
  --print-links
```

`--reset-inbound` удаляет старый VLESS inbound с тем же портом и remark, затем
создаёт новый. Используй этот флаг при первичной настройке, смене Reality target,
перегенерации Reality keypair или исправлении нерабочего inbound.

После команды проверь диагностику:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops vpn-diagnose
```

Ожидаемые признаки:

```text
stream: tcp + reality
reality target: www.amazon.com:443
reality sni: www.amazon.com
keys present: private=True public=True
clients: 3 (main, partner, shared)
warnings: none
```

Проверь порты:

```bash
sudo ss -tlnp | grep -E ':443|:ПОРТ_ПАНЕЛИ'
sudo ufw status
systemctl status x-ui --no-pager
```

Ожидаемо:

```text
*:443
127.0.0.1:ПОРТ_ПАНЕЛИ
22/tcp ALLOW
443/tcp ALLOW
```

## Шаг 9. Импорт в Hiddify

Для первого теста используй профиль `main`.

1. Скопируй ссылку `main` из вывода `bootstrap-vpn`.
2. Не отправляй ссылку в чат и не сохраняй её в git.
3. В Hiddify добавь профиль из буфера обмена.
4. Выбери профиль и подключись.
5. Открой сайт, который должен идти через VPN.
6. Вернись в 3x-ui и проверь, что у inbound `vless-reality-vision` растёт трафик.

Если Hiddify показывает `unknown IP`, значит ссылка собрана без публичного host.
Проверь:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops public-host
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops vpn-diagnose
```

Если host неверный, укажи `MIRAGE_XUI_PUBLIC_HOST` в `.env.local` и снова
выполни `bootstrap-vpn --reset-inbound --print-links`.

Если Hiddify зависает на timeout:

```bash
sudo ss -tlnp | grep ':443'
sudo ufw status
sudo journalctl -u x-ui -n 100 --no-pager
```

Порт `443/tcp` должен слушать `xray-linux-amd64`, а `ufw` должен разрешать
`443/tcp`.

## Шаг 10. Первый бэкап

После успешной проверки сделай backup базы 3x-ui:

```bash
mkdir -p backups/x-ui
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops backup-db
```

Сохрани копию вне репозитория: в защищённую папку, зашифрованное облако или
менеджер паролей с поддержкой файлов.

Подробный порядок:
[runbook бэкапа 3x-ui](../runbooks/backup-xui.md).

## Итоговая проверка

- [ ] SSH работает только по ключу.
- [ ] `ufw` открывает `22/tcp` и `443/tcp`.
- [ ] Панель 3x-ui слушает `127.0.0.1:ПОРТ_ПАНЕЛИ`.
- [ ] Xray слушает `*:443`.
- [ ] `vpn-diagnose` не показывает предупреждений.
- [ ] Профиль `main` работает в Hiddify.
- [ ] Профили `partner` и `shared` созданы.
- [ ] Backup 3x-ui сохранён вне git.

Дальнейшая эксплуатация описана в
[docs/operations/README.md](../operations/README.md).
