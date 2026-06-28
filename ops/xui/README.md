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
   MIRAGE_XUI_BASE_URL=http://127.0.0.1:PANEL_PORT/WEB_BASE_PATH
   MIRAGE_XUI_PUBLIC_HOST=SERVER_HOST_OR_DOMAIN
   MIRAGE_XUI_API_TOKEN=PASTE_API_TOKEN_HERE
   MIRAGE_XUI_TUNNEL_LOCAL_PORT=2096
   MIRAGE_SSH_HOST=SERVER_HOST_OR_DOMAIN
   MIRAGE_SSH_USER=mirage
   MIRAGE_SSH_KEY=$HOME\.ssh\mirage_ed25519
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

Показать URL кабинета, SSH-туннель и частые команды:

```bash
py -3 ops/xui/xui_api.py access-info
```

Создать клиента и вывести готовую ссылку:

```bash
py -3 ops/xui/xui_api.py ensure-client --email main --print-links
```

Синхронизировать клиентов из локального файла:

```bash
py -3 ops/xui/xui_api.py sync-users --print-links
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

1. Собери образ из корня репозитория:

   ```bash
   docker compose -f ops/xui/compose.yml build
   ```

2. Создай `ops/xui/.env.local`:

   ```text
   MIRAGE_XUI_BASE_URL=http://127.0.0.1:ПОРТ_ПАНЕЛИ/WEB_BASE_PATH
   MIRAGE_XUI_API_TOKEN=PASTE_API_TOKEN_HERE
   MIRAGE_XUI_PUBLIC_HOST=SERVER_HOST_OR_DOMAIN
   MIRAGE_XUI_TUNNEL_LOCAL_PORT=2096
   MIRAGE_SSH_HOST=SERVER_HOST_OR_DOMAIN
   MIRAGE_SSH_USER=mirage
   MIRAGE_SSH_KEY=$HOME\.ssh\mirage_ed25519
   ```

3. Проверь доступ к панели:

   ```bash
   docker compose -f ops/xui/compose.yml run --rm xui-ops inbounds
   ```

4. Выведи URL кабинета, SSH-туннель и частые команды:

   ```bash
   docker compose -f ops/xui/compose.yml run --rm xui-ops access-info
   ```

5. Создай клиента и выведи ссылку:

   ```bash
   docker compose -f ops/xui/compose.yml run --rm xui-ops ensure-client --email CLIENT_EMAIL --print-links
   ```

6. Синхронизируй клиентов:

   ```bash
   docker compose -f ops/xui/compose.yml run --rm xui-ops sync-users --print-links
   ```

   По умолчанию будут созданы профили `main`, `partner` и `shared`.
   Если нужен другой список, скопируй `ops/xui/users.example.json` в
   `ops/xui/users.local.json` и измени локальный файл.

7. Скачай backup базы в локальную папку `backups/x-ui`:

   ```bash
   mkdir -p backups/x-ui
   docker compose -f ops/xui/compose.yml run --rm xui-ops backup-db
   ```

## Быстрый вход в кабинет с Windows

Скрипт `open-panel.ps1` запускается на локальном ПК. Он подключается к VPS по
SSH, получает `access-info` из контейнера, открывает SSH-туннель и запускает
браузер с правильным URL кабинета.

```powershell
.\ops\xui\open-panel.ps1 -ServerHost SERVER_HOST_OR_DOMAIN
```

Если SSH-ключ лежит не в `$HOME\.ssh\mirage_ed25519`, передай путь явно:

```powershell
.\ops\xui\open-panel.ps1 -ServerHost SERVER_HOST_OR_DOMAIN -KeyPath C:\PATH\TO\KEY
```

Если ключ защищён passphrase, введи его в открывшемся окне туннеля. Не закрывай
это окно, пока работаешь с кабинетом.
