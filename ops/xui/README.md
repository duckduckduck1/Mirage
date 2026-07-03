# xui-ops

`xui-ops` — CLI для управления 3x-ui через API. Deploy использует его для
создания inbound, профилей, ссылок и диагностики.

Основной порядок установки и работы описан в [руководстве](../../docs/guide.md).

## Запуск

На VPS:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops COMMAND
```

Контейнер использует host network, чтобы обращаться к 3x-ui на
`127.0.0.1:ПОРТ_ПАНЕЛИ`.

## Env-файл

`ops/vpn/deploy.sh` создаёт `ops/xui/.env.local` автоматически. Основные
переменные:

```text
MIRAGE_XUI_BASE_URL=http://127.0.0.1:ПОРТ_ПАНЕЛИ/WEB_BASE_PATH
MIRAGE_XUI_API_TOKEN=PASTE_TOKEN
MIRAGE_XUI_PUBLIC_HOST=SERVER_HOST_OR_DOMAIN
MIRAGE_XUI_VLESS_PORT=443
MIRAGE_XUI_REALITY_TARGET=www.amazon.com:443
MIRAGE_XUI_REALITY_SNI=www.amazon.com
```

## Команды

| Задача | Команда |
|---|---|
| Показать inbound'ы | `sudo docker compose -f ops/xui/compose.yml run --rm xui-ops inbounds` |
| Показать доступы без client links | `sudo docker compose -f ops/xui/compose.yml run --rm xui-ops access-info` |
| Проверить VPN | `sudo docker compose -f ops/xui/compose.yml run --rm xui-ops vpn-diagnose` |
| Получить профиль | `sudo docker compose -f ops/xui/compose.yml run --rm xui-ops subscriptions --email main` |
| Получить поля для V2RayTun | `sudo docker compose -f ops/xui/compose.yml run --rm xui-ops subscriptions --email main --target v2raytun` |
| Сделать backup через API 3x-ui | `sudo docker compose -f ops/xui/compose.yml run --rm xui-ops backup-db` |

Создать профиль:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops ensure-client \
  --email CLIENT_NAME \
  --print-links
```

Пересоздать VLESS Reality inbound:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops bootstrap-vpn \
  --reset-inbound \
  --reality-target www.amazon.com:443 \
  --reality-sni www.amazon.com \
  --print-links
```

## Открыть 3x-ui

С Windows:

```powershell
.\ops\xui\open-panel.ps1 -ServerHost SERVER_HOST_OR_DOMAIN
```

Скрипт открывает кабинет 3x-ui. Mirage Admin открывается отдельным туннелем на
`8090`.

## Локальная разработка

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r ops\xui\requirements.txt
.\.venv\Scripts\python.exe ops\xui\xui_api.py --help
```

Команды, которые выводят клиентские ссылки, считай секретными.
