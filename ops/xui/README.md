# xui-ops

`xui-ops` — CLI для управления 3x-ui через HTTP API. В v0.1 основной пользователь
работает через Mirage Admin, а `xui-ops` остаётся техническим инструментом для
deploy, диагностики и ручных операций.

Основной путь установки: [развёртывание на VPS](../../docs/deploy.md).
Ежедневная работа: [эксплуатация](../../docs/operations.md).

## Запуск

На VPS:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops COMMAND
```

Контейнер использует host network, чтобы видеть 3x-ui на
`127.0.0.1:ПОРТ_ПАНЕЛИ`.

Локально для разработки:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r ops\xui\requirements.txt
.\.venv\Scripts\python.exe ops\xui\xui_api.py --help
```

## Конфигурация

Локальный env-файл на VPS:

```bash
cp ops/xui/.env.example ops/xui/.env.local
```

Минимальные переменные:

```text
MIRAGE_XUI_BASE_URL=http://127.0.0.1:ПОРТ_ПАНЕЛИ/WEB_BASE_PATH
MIRAGE_XUI_API_TOKEN=PASTE_TOKEN
MIRAGE_XUI_PUBLIC_HOST=SERVER_HOST_OR_DOMAIN
MIRAGE_XUI_VLESS_PORT=443
MIRAGE_XUI_REALITY_TARGET=www.amazon.com:443
MIRAGE_XUI_REALITY_SNI=www.amazon.com
```

`ops/vpn/deploy.sh` заполняет этот файл автоматически.

## Частые команды

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops inbounds
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops access-info
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops vpn-diagnose
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops subscriptions --email main
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops subscriptions --email main --target v2raytun
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops backup-db
```

Пересоздать VLESS Reality inbound:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops bootstrap-vpn \
  --reset-inbound \
  --reality-target www.amazon.com:443 \
  --reality-sni www.amazon.com \
  --print-links
```

Создать клиента:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops ensure-client \
  --email CLIENT_NAME \
  --print-links
```

## Быстрый вход в 3x-ui

С Windows:

```powershell
.\ops\xui\open-panel.ps1 -ServerHost SERVER_HOST_OR_DOMAIN
```

Скрипт открывает именно кабинет 3x-ui. Mirage Admin открывай отдельным
SSH-туннелем на `8090`, как описано в [эксплуатации](../../docs/operations.md).

## Безопасность

`vpn-diagnose` не печатает клиентские ссылки, UUID, short IDs и ключи. Команды,
которые выводят ссылки, считай секретными.
