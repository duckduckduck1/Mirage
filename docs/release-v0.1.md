# Release-check v0.1

Этот чек-лист используется перед PR `dev` → `main` и тегом `v0.1.0`. Он
подтверждает, что Mirage разворачивается на VPS, держит закрытыми панели,
создаёт рабочие профили и не тащит секреты в репозиторий.

Не копируй в PR, issue, чат или документацию реальные IP, домены, ссылки, token,
пароли, `WEB_BASE_PATH`, UUID, private key Reality и backup-файлы.

## 1. Обнови VPS

```bash
cd /home/mirage/projects/Mirage
git switch dev
git pull --ff-only origin dev
git status --short --branch
```

Ожидаемо: ветка `dev`, рабочее дерево чистое.

## 2. Запусти release gate

```bash
sudo -E bash ops/release/check-local.sh
```

Ожидаемо:

```text
Release gate passed
```

Blocker:

- падают unit-тесты;
- не собираются Docker images;
- secret guard находит секреты;
- Docker Compose config не проходит.

## 3. Проверь deploy

```bash
export SERVER=SERVER_HOST_OR_DOMAIN
sudo bash ops/vpn/deploy.sh "$SERVER"
```

Ожидаемо:

- deploy завершается строкой `Done`;
- создан `/home/mirage/mirage-vpn/access.md`;
- созданы профили в `/home/mirage/mirage-vpn/links/`;
- создана директория `/home/mirage/mirage-vpn/backups/`;
- права на access bundle и links закрыты для посторонних.

Проверь права:

```bash
namei -l /home/mirage/mirage-vpn
ls -ld /home/mirage/mirage-vpn /home/mirage/mirage-vpn/links /home/mirage/mirage-vpn/backups
ls -l /home/mirage/mirage-vpn/access.md /home/mirage/mirage-vpn/links
```

## 4. Проверь сервисы и firewall

```bash
PANEL_PORT="$(
  sudo sed -n 's#^MIRAGE_XUI_BASE_URL=http://127\.0\.0\.1:\([0-9][0-9]*\)/.*#\1#p' \
    ops/xui/.env.local
)"

systemctl is-active --quiet x-ui
sudo ss -tlnp | grep -E "(:443\b|127\.0\.0\.1:${PANEL_PORT}\b|127\.0\.0\.1:8090\b)"
sudo ufw status numbered
```

Ожидаемо:

- Xray слушает `*:443`;
- 3x-ui слушает `127.0.0.1:$PANEL_PORT`;
- Mirage Admin слушает `127.0.0.1:8090`;
- в `ufw` нет публичных правил для `8090`, `$PANEL_PORT`, `8388`, `8443`,
  `9443`, `2096`.

С локальной машины:

```powershell
$Server = "SERVER_HOST_OR_DOMAIN"
$PanelPort = PANEL_PORT

Test-NetConnection $Server -Port 443
Test-NetConnection $Server -Port 8090
Test-NetConnection $Server -Port $PanelPort
```

Замени `SERVER_HOST_OR_DOMAIN` на адрес VPS, а `PANEL_PORT` — на число из
`/home/mirage/mirage-vpn/access.md` или `ops/xui/.env.local`.

Ожидаемо: `443` доступен, `8090` и `$PanelPort` недоступны.

## 5. Проверь VLESS Reality

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
```

Ожидаемо: команда возвращает `true`.

## 6. Проверь Mirage Admin API

```bash
MIRAGE_ADMIN_TOKEN="$(
  sudo awk -F= '/^MIRAGE_ADMIN_TOKEN=/ {print $2; exit}' ops/admin/.env.local
)"

curl -fsS http://127.0.0.1:8090/healthz | jq -e '.status == "ok"'

curl -s -o /dev/null -w '%{http_code}\n' \
  http://127.0.0.1:8090/api/v0/health

curl -fsS -H "Authorization: Bearer $MIRAGE_ADMIN_TOKEN" \
  http://127.0.0.1:8090/api/v0/health \
  | jq -e '.status == "ok" and all(.checks[]; .ok == true)'
```

Ожидаемо:

- `/healthz` возвращает `ok`;
- API без token возвращает `401`;
- API с token возвращает `true`.

## 7. Проверь backup и restore-helper

```bash
sudo systemctl is-enabled --quiet mirage-xui-backup.timer
sudo systemctl is-active --quiet mirage-xui-backup.timer
sudo systemctl is-enabled --quiet mirage-admin-restore.path
sudo systemctl is-active --quiet mirage-admin-restore.path
```

Создай backup через API:

```bash
BACKUP="$(
  curl -fsS -X POST -H "Authorization: Bearer $MIRAGE_ADMIN_TOKEN" \
    http://127.0.0.1:8090/api/v0/backups \
    | jq -r '.name'
)"

curl -fsS -H "Authorization: Bearer $MIRAGE_ADMIN_TOKEN" \
  http://127.0.0.1:8090/api/v0/backups \
  | jq -e --arg backup "$BACKUP" 'any(.backups[]; .name == $backup)'
```

Restore проверяй только на disposable smoke VPS или в окно обслуживания.

## 8. Проверь клиент

1. Удали старый профиль из VPN-клиента.
2. Возьми свежий профиль из Mirage Admin или
   `/home/mirage/mirage-vpn/links/main.profile.txt`.
3. Импортируй профиль в Hiddify.
4. Подключись и проверь трафик.
5. Проверь, что в Mirage Admin или 3x-ui растёт трафик у `main`.

Для V2RayTun сверь ручные поля:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops subscriptions \
  --email main --target v2raytun
```

## 9. Проверь секреты

```bash
git status --short --ignored=no
git ls-files ops/xui/.env.local ops/admin/.env.local
git ls-files '*.db' 'backups/*' 'secrets/*' 'exports/*'
```

Ожидаемо: команды с `git ls-files` ничего не выводят.

## Решение о выпуске

`v0.1.0` можно выпускать, если:

- release gate прошёл;
- deploy воспроизводимо проходит на VPS;
- `443/tcp` работает;
- Mirage Admin и 3x-ui закрыты извне;
- Admin API требует token;
- backup создаётся;
- минимум один desktop или mobile-клиент подключается;
- в репозитории нет секретов.

После успешной проверки открой PR `dev` → `main`, затем поставь тег `v0.1.0`.
