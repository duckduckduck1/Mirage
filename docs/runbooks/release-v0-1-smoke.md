# Smoke-check v0.1

Этот runbook используется перед выпуском `v0.1`: после merge всех feature-веток
в `dev`, перед PR `dev` → `main` и тегом релиза.

Проверка подтверждает, что на VPS разворачивается полный рабочий контур Mirage:
VLESS Reality на `443/tcp`, локальная админ-панель, профили участников, backup,
restore helper, Telegram alerts и защита секретов.

Не копируй в issue, PR, чат или документацию реальные IP, домены, клиентские
ссылки, токены, пароли, `WEB_BASE_PATH`, UUID, private key Reality и backup-файлы.

## Предусловия

- Ветка `dev` содержит все изменения, которые должны войти в `v0.1`.
- CI зелёный.
- VPS доступен по SSH под пользователем `mirage`.
- Docker установлен.
- Node.js установлен для локальной проверки JavaScript в release gate.
- Репозиторий находится в `/home/mirage/projects/Mirage`.
- Проверка выполняется на тестовом или текущем VPS, где допустим короткий
  перезапуск `x-ui` при проверке restore.

На VPS:

```bash
cd /home/mirage/projects/Mirage
git switch dev
git pull --ff-only origin dev
export SERVER=SERVER_HOST_OR_DOMAIN
```

`SERVER_HOST_OR_DOMAIN` — публичный адрес, который будет попадать в клиентские
ссылки. Для финального релиза предпочтителен домен; до подключения домена можно
использовать публичный IP, но не коммитить его.

## 1. Release gate

На VPS выполни полный release gate:

```bash
node --version || sudo apt-get install -y nodejs
bash ops/release/check-local.sh
```

Ожидаемо:

- команда завершается без ошибок;
- в конце выведено `Release gate passed`;
- unit-тесты, shell syntax, frontend smoke, docker build и secret guard прошли.

`--skip-docker` можно использовать только для быстрой локальной проверки на ПК.
Для release candidate нужен полный прогон без этого флага.

Blocker:

- падают unit-тесты;
- не собирается Docker image;
- `git diff --check` или secret guard находят проблему;
- в tracked-файлах обнаружены реальные `.env`, backup, ключи или клиентские
  ссылки.

## 2. Deploy

На VPS:

```bash
git status --short --branch
sudo bash ops/vpn/deploy.sh "$SERVER"
```

Ожидаемо:

- ветка чистая;
- deploy завершается строкой `Done`;
- создан `/home/mirage/mirage-vpn/access.md`;
- созданы файлы профилей в `/home/mirage/mirage-vpn/links/`;
- создана директория backup;
- файлы доступа и ссылок имеют права только для владельца.

Проверь права:

```bash
namei -l /home/mirage/mirage-vpn
ls -ld /home/mirage/mirage-vpn /home/mirage/mirage-vpn/links
ls -l /home/mirage/mirage-vpn/access.md /home/mirage/mirage-vpn/links
```

Blocker:

- deploy завершился с ошибкой;
- не создан API token;
- отсутствует профиль `main`, `partner` или `shared`;
- `access.md`, links или backups доступны не только владельцу.

## 3. Сервисы, bind и firewall

На VPS:

```bash
PANEL_PORT="$(
  sed -n 's#^MIRAGE_XUI_BASE_URL=http://127\.0\.0\.1:\([0-9][0-9]*\)/.*#\1#p' \
    ops/xui/.env.local
)"

systemctl is-active --quiet x-ui
sudo ss -tlnp | grep -E "127.0.0.1:${PANEL_PORT}|127.0.0.1:8090|:443"
sudo ufw status numbered
```

Ожидаемо:

- `x-ui` active;
- Xray слушает `*:443`;
- 3x-ui слушает только `127.0.0.1:$PANEL_PORT`;
- Mirage Admin слушает только `127.0.0.1:8090`;
- `ufw` разрешает только нужные публичные порты: `22/tcp` и `443/tcp`.

Blocker:

- `443/tcp` не слушается;
- порт панели 3x-ui доступен на публичном интерфейсе;
- Mirage Admin доступен на публичном интерфейсе;
- в `ufw` остались лишние публичные правила для `8388`, `8443`, `9443`, `2096`,
  порта панели или `8090`.

## 4. VLESS Reality и профили

На VPS:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops --json vpn-diagnose \
  | jq -e '.warnings == []
    and .inbound.protocol == "vless"
    and .inbound.port == 443
    and .inbound.network == "tcp"
    and .inbound.security == "reality"
    and .inbound.privateKeyPresent
    and .inbound.publicKeyPresent
    and (.inbound.clients | sort) == ["main","partner","shared"]'

sudo docker compose -f ops/xui/compose.yml run --rm xui-ops public-host

for user in main partner shared; do
  sudo docker compose -f ops/xui/compose.yml run --rm xui-ops links --email "$user" \
    | grep -q '^vless://'
done
```

Ожидаемо:

- diagnostics не содержит warnings;
- inbound — `VLESS + TCP + Reality` на `443/tcp`;
- Reality keypair и short IDs присутствуют;
- target/SNI соответствуют текущей рабочей конфигурации;
- public host совпадает с `$SERVER`;
- у `main`, `partner`, `shared` есть клиентские ссылки.

Blocker:

- diagnostics показывает warning;
- inbound отсутствует или не `VLESS Reality`;
- public host не совпадает с `$SERVER`;
- отсутствует любой из базовых профилей;
- клиентская ссылка собирается без публичного host.

## 5. Mirage Admin API

На VPS:

```bash
MIRAGE_ADMIN_TOKEN="$(
  sudo awk -F= '/^MIRAGE_ADMIN_TOKEN=/ {print $2; exit}' ops/admin/.env.local
)"
export MIRAGE_ADMIN_TOKEN

curl -fsS http://127.0.0.1:8090/healthz | jq -e '.status == "ok"'

curl -s -o /dev/null -w '%{http_code}\n' \
  http://127.0.0.1:8090/api/v0/health

curl -fsS -H "Authorization: Bearer $MIRAGE_ADMIN_TOKEN" \
  http://127.0.0.1:8090/api/v0/health \
  | jq -e '.status == "ok" and all(.checks[]; .ok == true)'

curl -fsS -H "Authorization: Bearer $MIRAGE_ADMIN_TOKEN" \
  http://127.0.0.1:8090/api/v0/profiles \
  | jq -e '.inbound.port == 443
    and ([.profiles[].email] | sort) == ["main","partner","shared"]'
```

Ожидаемо:

- `/healthz` возвращает `ok`;
- API без token возвращает `401`;
- API с token возвращает health `ok`;
- checks `xuiApi`, `vlessInbound`, `vpnPort443`, `backupDir` зелёные;
- список профилей содержит `main`, `partner`, `shared`.

Blocker:

- API доступен без token;
- health `degraded`;
- отсутствует любой базовый профиль;
- Admin API не стартует или не отвечает локально.

## 6. Backup timer и restore helper

На VPS:

```bash
sudo systemctl is-enabled --quiet mirage-xui-backup.timer
sudo systemctl is-active --quiet mirage-xui-backup.timer
sudo systemctl is-enabled --quiet mirage-admin-restore.path
sudo systemctl is-active --quiet mirage-admin-restore.path
```

Создай backup через Admin API:

```bash
BACKUP="$(
  curl -fsS -X POST -H "Authorization: Bearer $MIRAGE_ADMIN_TOKEN" \
    http://127.0.0.1:8090/api/v0/backups \
    | jq -r '.name'
)"

curl -fsS -H "Authorization: Bearer $MIRAGE_ADMIN_TOKEN" \
  http://127.0.0.1:8090/api/v0/backups \
  | jq -e --arg backup "$BACKUP" \
    '.policy.retentionDays == 14
      and .policy.keepMin == 3
      and any(.backups[]; .name == $backup)'
```

На disposable smoke VPS дополнительно проверь restore свежего backup:

```bash
JOB="$(
  curl -fsS -X POST \
    -H "Authorization: Bearer $MIRAGE_ADMIN_TOKEN" \
    -H 'Content-Type: application/json' \
    --data "{\"confirm\":\"restore\",\"confirmName\":\"$BACKUP\",\"ackDowntime\":true}" \
    "http://127.0.0.1:8090/api/v0/backups/$BACKUP/restore" \
    | jq -r '.jobId'
)"

for attempt in $(seq 1 12); do
  curl -fsS -H "Authorization: Bearer $MIRAGE_ADMIN_TOKEN" \
    "http://127.0.0.1:8090/api/v0/restore-requests/$JOB" \
    | jq -e '.status == "success"' && break
  sleep 2
done

systemctl is-active --quiet x-ui
```

Restore временно прерывает VPN-сервис. На production VPS выполняй его только если
есть окно обслуживания или если это отдельный smoke-сервер.

Blocker:

- backup timer disabled или inactive;
- restore path disabled или inactive;
- backup API не создаёт SQLite backup;
- restore job завершается ошибкой или зависает;
- после restore `x-ui` не active.

## 7. Локальный вход в админку

На Windows-ПК:

```powershell
.\ops\xui\open-panel.ps1 -ServerHost SERVER_HOST_OR_DOMAIN
```

Ожидаемо:

- открывается SSH-туннель;
- браузер открывает локальный URL;
- Admin UI требует token;
- после ввода token видны health, профили, links, backups и alerts.

Дополнительно проверь, что публично доступны только нужные порты:

```powershell
Test-NetConnection SERVER_HOST_OR_DOMAIN -Port 443
Test-NetConnection SERVER_HOST_OR_DOMAIN -Port 8090
Test-NetConnection SERVER_HOST_OR_DOMAIN -Port PANEL_PORT
```

Ожидаемо:

- `443` доступен;
- `8090` и `PANEL_PORT` снаружи недоступны.

Blocker:

- админка или 3x-ui открываются без SSH-туннеля;
- Admin UI не принимает действующий token;
- локальный туннель не открывается.

## 8. Проверка клиентов

Проверь минимум один desktop-клиент и один mobile-клиент.

Рекомендуемый порядок:

1. Удали старый профиль из VPN-приложения.
2. Возьми свежий профиль из `/home/mirage/mirage-vpn/links/main.profile.txt` или
   через Admin UI.
3. Импортируй профиль в Hiddify.
4. Подключись и открой несколько сайтов, включая сервисы, ради которых нужен VPN.
5. Если используется V2RayTun, импортируй ссылку и сверь ручные поля с выводом:

   ```bash
   sudo docker compose -f ops/xui/compose.yml run --rm xui-ops subscriptions \
     --email main --target v2raytun
   ```

6. В 3x-ui или Admin UI проверь, что у выбранного профиля растёт трафик.

Blocker:

- Hiddify показывает `timeout` или `unknown IP`;
- V2RayTun импортирует профиль, но трафик не идёт даже после ручной сверки полей;
- трафик не растёт у активного профиля;
- один из базовых профилей не подключается.

## 9. Alerts

Если Telegram alerts включены в `ops/admin/.env.local`, проверь тестовое
уведомление из Admin UI или через API:

```bash
curl -fsS -X POST -H "Authorization: Bearer $MIRAGE_ADMIN_TOKEN" \
  http://127.0.0.1:8090/api/v0/alerts/test
```

Ожидаемо:

- Telegram получает тестовое уведомление;
- уведомление не содержит token, пароль, клиентскую ссылку, `WEB_BASE_PATH` или
  private key.

Если alerts выключены, это не blocker для v0.1. В этом случае в Admin UI должен
быть понятный статус `disabled`.

## 10. Чистота репозитория и секретов

На VPS:

```bash
git status --short --ignored=no
git ls-files ops/xui/.env.local ops/admin/.env.local
git ls-files '*.db' 'backups/*' 'secrets/*' 'exports/*'
```

Ожидаемо:

- в tracked-файлах нет `.env.local`;
- backup-файлы не tracked;
- access bundle, links и generated secrets не tracked;
- рабочая ветка чистая или содержит только осознанные локальные ignored-файлы.

Blocker:

- в git попали реальные `.env.local`, token, пароль, клиентская ссылка, backup,
  private key или файл базы.

## Решение о выпуске

`v0.1` можно выпускать, если:

- полный release gate прошёл;
- deploy воспроизводимо проходит на VPS;
- `443/tcp` работает, а локальные панели не открыты наружу;
- Admin API требует token и показывает health `ok`;
- backup создаётся, timer активен, restore helper установлен;
- минимум один desktop и один mobile-клиент успешно подключаются;
- в репозитории нет секретов и backup-файлов.

После успешного smoke-check:

1. Открой PR `dev` → `main`.
2. После merge поставь тег `v0.1.0`.
3. Удали короткоживущие ветки локально и на GitHub.
