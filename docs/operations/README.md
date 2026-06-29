# Эксплуатация VPN

Этот документ описывает ежедневную работу с уже поднятым Mirage VPN: как открыть
кабинет 3x-ui, посмотреть состояние, выдать ссылку участнику, добавить нового
клиента, пересоздать inbound и сделать backup.

Все команды выполняй из корня репозитория на VPS:

```bash
cd /home/mirage/projects/Mirage
```

Секреты не добавляй в git: клиентские ссылки, UUID, API token, пароль панели,
`WEB_BASE_PATH`, Reality private key, short IDs и backup-файлы.

## Быстрый вход в кабинет

С локального Windows-ПК можно открыть кабинет одной командой:

```powershell
.\ops\xui\open-panel.ps1 -ServerHost SERVER_HOST_OR_DOMAIN
```

Скрипт подключается к VPS по SSH, получает `access-info`, открывает SSH-туннель и
запускает браузер с правильным URL.

Если ключ лежит не в `$HOME\.ssh\mirage_ed25519`:

```powershell
.\ops\xui\open-panel.ps1 -ServerHost SERVER_HOST_OR_DOMAIN -KeyPath C:\PATH\TO\KEY
```

Окно SSH-туннеля не закрывай, пока работаешь с панелью.

## Ручной SSH-туннель

На VPS посмотри параметры доступа:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops access-info
```

Команда покажет:

- порт панели на VPS;
- локальный URL кабинета;
- готовую команду SSH-туннеля;
- частые команды `xui-ops`.

На локальной машине открой туннель:

```powershell
ssh -i $HOME\.ssh\mirage_ed25519 -N -L 2096:127.0.0.1:ПОРТ_ПАНЕЛИ mirage@SERVER_HOST_OR_DOMAIN
```

Затем открой в браузере:

```text
http://127.0.0.1:2096/WEB_BASE_PATH
```

## Где взять логин, пароль и web path

Порт панели и `WEB_BASE_PATH`:

```bash
sudo /usr/local/x-ui/x-ui setting -show true
```

Результат установки:

```bash
sudo cat /etc/x-ui/install-result.env
```

Файл может содержать логин, пароль и URL панели. Не копируй его во внешние
каналы.

Если пароль потерян:

```bash
sudo /usr/local/x-ui/x-ui
```

В меню выбери пункт изменения логина или пароля. После смены обнови
`ops/xui/.env.local`, если там временно использовались логин и пароль. Лучше
используй API token.

## Проверка состояния

Быстрая проверка VPN:

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

Проверка портов:

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
x-ui active (running)
```

Показать inbound'ы:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops inbounds
```

Показать публичный host для ссылок:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops public-host
```

## Модель участников

По умолчанию `xui-ops` создаёт три профиля:

| Профиль | Назначение |
|---|---|
| `main` | основной профиль владельца |
| `partner` | отдельный профиль для близкого участника |
| `shared` | общий профиль для остальных |

Не используй один и тот же профиль для всех, если тебе важны отключение доступа,
ротация и понятная статистика. Минимальная практичная схема — `main`, `partner`,
`shared`.

## Получить ссылки

Вывести прямую ссылку конкретного профиля:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops links --email main
```

Для другого профиля:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops links --email partner
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops links --email shared
```

Вывести subscription-ссылки клиента, если они включены в 3x-ui:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops sub-links --email main
```

Ссылки содержат секрет подключения. Храни их в менеджере паролей и передавай
только адресату.

## Добавить нового участника

Для одного участника:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops ensure-client \
  --email CLIENT_EMAIL \
  --print-links
```

`CLIENT_EMAIL` — короткий технический идентификатор, например `friend-a` или
`tablet`. Не используй реальные ФИО и личные данные.

Проверить, что клиент привязан к inbound:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops vpn-diagnose
```

## Синхронизировать список клиентов

Если нужен свой список профилей, создай локальный файл:

```bash
cp ops/xui/users.example.json ops/xui/users.local.json
nano ops/xui/users.local.json
```

Пример структуры:

```json
{
  "clients": [
    {
      "email": "main",
      "comment": "owner devices",
      "group": "default"
    },
    {
      "email": "partner",
      "comment": "partner devices",
      "group": "default"
    },
    {
      "email": "shared",
      "comment": "shared access",
      "group": "default"
    }
  ]
}
```

Синхронизируй:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops sync-users --print-links
```

`users.local.json` игнорируется git.

## Обновить ссылки

Для одного участника:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops links --email CLIENT_EMAIL
```

Для всех участников из `users.local.json` или дефолтного списка:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops sync-users --print-links
```

Если менялся public host, домен или Reality target, сначала пересоздай inbound,
затем выдай новые ссылки.

## Пересоздать VPN inbound

Используй reset, если:

- меняешь Reality target или SNI;
- Hiddify показывает timeout при доступном `443/tcp`;
- клиент показывает `unknown IP`;
- нужно перегенерировать Reality keypair;
- inbound был создан вручную с ошибочными параметрами.

Перед reset сделай backup:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops backup-db
```

Затем пересоздай inbound:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops bootstrap-vpn \
  --reset-inbound \
  --reality-target www.amazon.com:443 \
  --reality-sni www.amazon.com \
  --print-links
```

После reset импортируй свежие ссылки в Hiddify. Старые профили удали или отключи
в клиентском приложении.

## Отключить или удалить клиента

Отключить:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops disable-client --email CLIENT_EMAIL
```

Включить обратно:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops enable-client --email CLIENT_EMAIL
```

Удалить:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops delete-client --email CLIENT_EMAIL
```

Перед массовым удалением сделай backup.

## Бэкап

Скачать backup базы 3x-ui через API:

```bash
mkdir -p backups/x-ui
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops backup-db
```

Папка `backups/` игнорируется git. Для защиты от потери данных держи вторую
копию вне рабочей папки проекта.

Подробно:
[runbook бэкапа 3x-ui](../runbooks/backup-xui.md).

## Новый протокол или порт

Добавляй новый inbound только отдельной операцией после backup.

Минимальный порядок:

1. Сделай backup 3x-ui.
2. Выбери протокол и порт.
3. Проверь, что порт свободен:

   ```bash
   sudo ss -tlnp | grep ':PORT' || true
   ```

4. Создай inbound в панели или отдельной автоматизацией.
5. Открой порт в `ufw`, если inbound должен быть публичным.
6. Проверь `ss`, `ufw`, клиент и рост трафика.
7. Сделай backup после проверки.

Shadowsocks-2022 сейчас остаётся fallback-экспериментом:
[runbook Shadowsocks-2022](../runbooks/setup-shadowsocks-2022.md).

## Диагностика проблем

### Hiddify показывает unknown IP

Проверь public host:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops public-host
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops vpn-diagnose
```

Если host неверный, задай `MIRAGE_XUI_PUBLIC_HOST` в `ops/xui/.env.local` и
пересоздай inbound с `--reset-inbound`.

### Hiddify зависает на timeout

Проверь порт, firewall и сервис:

```bash
sudo ss -tlnp | grep ':443'
sudo ufw status
systemctl status x-ui --no-pager
sudo journalctl -u x-ui -n 100 --no-pager
```

Если `443/tcp` доступен, но подключение не идёт, проверь `vpn-diagnose`:
Reality target, SNI, ключи, short IDs и список клиентов должны быть заполнены.

### Панель не открывается через туннель

Проверь, что `x-ui` запущен:

```bash
systemctl status x-ui --no-pager
sudo ss -tlnp | grep 'ПОРТ_ПАНЕЛИ'
```

Если сервис остановлен:

```bash
sudo systemctl start x-ui
```

Проверь `WEB_BASE_PATH`:

```bash
sudo /usr/local/x-ui/x-ui setting -show true
```

### API-команды не работают

Проверь `.env.local`:

```bash
sed -n '1,80p' ops/xui/.env.local
```

Не отправляй вывод наружу. Убедись, что заданы:

```text
MIRAGE_XUI_BASE_URL
MIRAGE_XUI_API_TOKEN
MIRAGE_XUI_PUBLIC_HOST
```

Проверь доступ:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops inbounds
```

Если token был сменён или удалён, создай новый через кабинет или временно через
логин/пароль, затем обнови `.env.local`.

## Операционный чек-лист

- [ ] Перед рискованным изменением сделан backup.
- [ ] Панель открывается только через SSH-туннель.
- [ ] `vpn-diagnose` не показывает предупреждений.
- [ ] `ufw` открывает только нужные порты.
- [ ] У каждого постоянного участника отдельный профиль.
- [ ] Новые ссылки сохранены вне git.
- [ ] После reset старые профили удалены из клиентских приложений.
