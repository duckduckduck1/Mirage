# xui-ops

`xui-ops` — CLI для управления 3x-ui через HTTP API. Он используется после
установки панели на VPS: создаёт VLESS Reality inbound, синхронизирует клиентов,
печатает ссылки, делает backup и показывает безопасную диагностику.

Полный путь установки описан в [гайде развёртывания](../../docs/setup/README.md).
Ежедневные операции описаны в
[гайде эксплуатации](../../docs/operations/README.md).

## Где запускается

На VPS запускай CLI в Docker-контейнере:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops COMMAND
```

Контейнер использует `network_mode: host`, чтобы видеть панель 3x-ui на
`127.0.0.1:ПОРТ_ПАНЕЛИ`.

Локально на Windows можно запускать Python-версию для разработки:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r ops\xui\requirements.txt
.\.venv\Scripts\python.exe ops\xui\xui_api.py --help
```

## Конфигурация

Создай локальный файл:

```bash
cp ops/xui/.env.example ops/xui/.env.local
```

Минимальный набор:

```text
MIRAGE_XUI_BASE_URL=http://127.0.0.1:ПОРТ_ПАНЕЛИ/WEB_BASE_PATH
MIRAGE_XUI_API_TOKEN=
MIRAGE_XUI_PUBLIC_HOST=SERVER_HOST_OR_DOMAIN
MIRAGE_XUI_TUNNEL_LOCAL_PORT=2096
MIRAGE_SSH_HOST=SERVER_HOST_OR_DOMAIN
MIRAGE_SSH_USER=mirage
MIRAGE_SSH_KEY=$HOME\.ssh\mirage_ed25519
MIRAGE_XUI_VLESS_PORT=443
MIRAGE_XUI_VLESS_REMARK=vless-reality-vision
MIRAGE_XUI_REALITY_TARGET=www.amazon.com:443
MIRAGE_XUI_REALITY_SNI=www.amazon.com
```

`WEB_BASE_PATH` смотри на VPS:

```bash
sudo /usr/local/x-ui/x-ui setting -show true
```

Если API token ещё не создан, временно очисти или закомментируй
`MIRAGE_XUI_API_TOKEN`, задай `MIRAGE_XUI_USERNAME` и `MIRAGE_XUI_PASSWORD`,
затем выполни:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops create-token --name mirage-ops
```

После получения token удали логин и пароль из `.env.local`.

## Основные команды

Собрать образ:

```bash
sudo docker compose -f ops/xui/compose.yml build
```

Показать inbound'ы:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops inbounds
```

Показать публичный host для клиентских ссылок:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops public-host
```

Показать URL кабинета, SSH-туннель и частые команды:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops access-info
```

Показать безопасную диагностику VLESS inbound:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops vpn-diagnose
```

Создать или пересоздать VPN inbound и профили `main`, `partner`, `shared`:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops bootstrap-vpn \
  --reset-inbound \
  --reality-target www.amazon.com:443 \
  --reality-sni www.amazon.com \
  --print-links
```

Создать клиента и вывести ссылку:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops ensure-client \
  --email CLIENT_EMAIL \
  --print-links
```

Синхронизировать клиентов из `users.local.json` или дефолтного списка:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops sync-users --print-links
```

Вывести ссылку клиента:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops links --email main
```

Вывести subscription-ссылки клиента:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops sub-links --email main
```

Отключить клиента:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops disable-client --email CLIENT_EMAIL
```

Скачать backup базы 3x-ui:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops backup-db
```

## Файлы

| Файл | Назначение |
|---|---|
| `.env.example` | пример переменных окружения |
| `.env.local` | локальные секреты, не коммитится |
| `users.example.json` | дефолтные профили `main`, `partner`, `shared` |
| `users.local.json` | локальный список клиентов, не коммитится |
| `compose.yml` | Docker-запуск CLI на VPS |
| `open-panel.ps1` | быстрый вход в кабинет с Windows |
| `xui_api.py` | основной CLI |

## Быстрый вход в кабинет

С Windows:

```powershell
.\ops\xui\open-panel.ps1 -ServerHost SERVER_HOST_OR_DOMAIN
```

Скрипт получает `access-info` с VPS, открывает SSH-туннель и запускает браузер.
Не закрывай окно туннеля, пока работаешь с кабинетом.

## Безопасность

`vpn-diagnose` не печатает клиентские ссылки, UUID, short IDs и ключи. Остальные
команды, которые выводят ссылки, считай секретными. Не копируй их в issue, PR,
документацию или чат.
