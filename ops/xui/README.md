# 3x-ui API automation

`xui_api.py` управляет установленной панелью 3x-ui через официальный HTTP API.
Скрипт не хранит секреты в репозитории: URL панели, API token и публичный адрес
передаются через `.env.local`, переменные окружения или аргументы командной
строки.

В Windows запускай команды через `py -3` или через локальный `.venv`. На Linux
используй `python3`.

## Локальный venv

Из корня репозитория:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r ops\xui\requirements.txt
.\.venv\Scripts\python.exe ops\xui\xui_api.py --help
```

## Базовая настройка

1. Открой SSH-туннель к панели:

   ```powershell
   ssh -i $HOME\.ssh\mirage_ed25519 -L 2096:127.0.0.1:ПОРТ_ПАНЕЛИ mirage@SERVER_HOST
   ```

2. Создай `ops/xui/.env.local` по примеру `ops/xui/.env.example`.

3. Укажи в `MIRAGE_XUI_BASE_URL` полный локальный URL панели с web base path:

   ```text
   MIRAGE_XUI_BASE_URL=http://127.0.0.1:2096/WEB_BASE_PATH
   MIRAGE_XUI_PUBLIC_HOST=SERVER_HOST_OR_DOMAIN
   MIRAGE_XUI_API_TOKEN=PASTE_API_TOKEN_HERE
   ```

Если API token ещё не создан, временно задай `MIRAGE_XUI_USERNAME` и
`MIRAGE_XUI_PASSWORD`, затем выполни:

```bash
py -3 ops/xui/xui_api.py create-token --name mirage-ops
```

Сохрани выданный token в `.env.local` и убери пароль панели из окружения.

## Команды

Показать inbound:

```bash
py -3 ops/xui/xui_api.py inbounds
```

Создать клиента и вывести готовую ссылку:

```bash
py -3 ops/xui/xui_api.py ensure-client --email main --print-links
```

Синхронизировать клиентов из локального файла:

```bash
py -3 ops/xui/xui_api.py sync-users --users ops/xui/users.local.json --print-links
```

Отключить старого клиента:

```bash
py -3 ops/xui/xui_api.py disable-client --email OLD_CLIENT_EMAIL
```

Скачать backup базы 3x-ui:

```bash
py -3 ops/xui/xui_api.py backup-db
```

`ops/xui/*.local.json`, `.env.local` и `backups/` игнорируются git.

## Запуск в контейнере на VPS

На VPS контейнер запускается с host network. Так он видит локальную 3x-ui панель,
которая слушает `127.0.0.1:ПОРТ_ПАНЕЛИ` на хосте.
По умолчанию контейнер пишет backup-файлы от UID/GID `1000:1000`. Если на VPS у
пользователя другой UID/GID, задай `MIRAGE_DOCKER_UID` и `MIRAGE_DOCKER_GID`
перед `docker compose`.

1. Собери образ из корня репозитория:

   ```bash
   docker compose -f ops/xui/compose.yml build
   ```

2. Создай `ops/xui/.env.local`:

   ```text
   MIRAGE_XUI_BASE_URL=http://127.0.0.1:ПОРТ_ПАНЕЛИ/WEB_BASE_PATH
   MIRAGE_XUI_API_TOKEN=PASTE_API_TOKEN_HERE
   MIRAGE_XUI_PUBLIC_HOST=SERVER_HOST_OR_DOMAIN
   ```

3. Проверь доступ к панели:

   ```bash
   docker compose -f ops/xui/compose.yml run --rm xui-ops inbounds
   ```

4. Создай клиента и выведи ссылку:

   ```bash
   docker compose -f ops/xui/compose.yml run --rm xui-ops ensure-client --email CLIENT_EMAIL --print-links
   ```

5. Скачай backup базы в локальную папку `backups/x-ui`:

   ```bash
   mkdir -p backups/x-ui
   docker compose -f ops/xui/compose.yml run --rm xui-ops backup-db
   ```
