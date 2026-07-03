# Эксплуатация

Этот документ описывает работу с уже поднятым Mirage VPN: как открыть админку,
выдать профиль, добавить участника, сделать backup, восстановиться и проверить
неисправности.

Команды на VPS выполняй из корня репозитория:

```bash
cd /home/mirage/projects/Mirage
```

Секреты не отправляй во внешние каналы: token, `WEB_BASE_PATH`, ссылки, UUID,
Reality private key, short IDs и backup-файлы.

## Где лежат данные доступа

Основной файл после deploy:

```bash
sudo cat /home/mirage/mirage-vpn/access.md
```

В нём есть:

- URL Mirage Admin после SSH-туннеля;
- команда SSH-туннеля для Mirage Admin;
- token Mirage Admin;
- параметры 3x-ui панели;
- пути к профилям `main`, `partner`, `shared`;
- директория backup.

Файл имеет права `600`. Храни его как секрет.

## Открыть Mirage Admin

На локальной машине:

```powershell
ssh -i $HOME\.ssh\mirage_ed25519 -N -L 8090:127.0.0.1:8090 mirage@SERVER_HOST_OR_DOMAIN
```

Открой:

```text
http://127.0.0.1:8090/
```

Введи `MIRAGE_ADMIN_TOKEN` из `/home/mirage/mirage-vpn/access.md`.

## Открыть 3x-ui

3x-ui нужен для ручной проверки низкого уровня. Основные операции делай через
Mirage Admin или `xui-ops`.

С Windows:

```powershell
.\ops\xui\open-panel.ps1 -ServerHost SERVER_HOST_OR_DOMAIN
```

Порт панели и `WEB_BASE_PATH` можно посмотреть на VPS:

```bash
sudo /usr/local/x-ui/x-ui setting -show true
```

Если пароль панели потерян:

```bash
sudo /usr/local/x-ui/x-ui
```

В меню выбери смену логина или пароля.

## Проверить состояние

Быстрая проверка через Admin API:

```bash
MIRAGE_ADMIN_TOKEN="$(
  sudo awk -F= '/^MIRAGE_ADMIN_TOKEN=/ {print $2; exit}' ops/admin/.env.local
)"

curl -fsS http://127.0.0.1:8090/healthz
curl -fsS -H "Authorization: Bearer $MIRAGE_ADMIN_TOKEN" \
  http://127.0.0.1:8090/api/v0/health
```

Проверка VPN:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops vpn-diagnose
sudo ss -tlnp | grep -E ':443|127.0.0.1:8090'
sudo ufw status numbered
```

Ожидаемо:

- `vpn-diagnose` без предупреждений;
- `443/tcp` слушает Xray;
- Mirage Admin слушает `127.0.0.1:8090`;
- публично открыт `443/tcp`, а не порт админки или панели.

## Профили участников

По умолчанию deploy создаёт:

| Профиль | Назначение |
|---|---|
| `main` | основной профиль владельца |
| `partner` | отдельный близкий профиль |
| `shared` | общий профиль для остальных |

Не используй один профиль для всех постоянных участников, если важны отключение
доступа, ротация и понятная статистика.

## Получить ссылку

Через Mirage Admin открой раздел профилей и выбери нужного участника.

Через CLI:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops subscriptions --email main
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops subscriptions --email main --target v2raytun
```

Файлы, созданные deploy:

```text
/home/mirage/mirage-vpn/links/main.profile.txt
/home/mirage/mirage-vpn/links/main.profile.json
/home/mirage/mirage-vpn/links/partner.profile.txt
/home/mirage/mirage-vpn/links/shared.profile.txt
```

Перед импортом в Hiddify удали старый профиль, затем добавь свежую ссылку.

## Добавить участника

Через Mirage Admin создай профиль с техническим именем. Не используй реальные
ФИО, номера телефонов или личные данные.

Через CLI:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops ensure-client \
  --email CLIENT_NAME \
  --print-links
```

Примеры технических имён: `friend-a`, `tablet`, `travel`.

## Отключить или удалить профиль

Через Mirage Admin открой профиль и выбери нужное действие.

Через CLI:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops disable-client --email CLIENT_NAME
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops enable-client --email CLIENT_NAME
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops delete-client --email CLIENT_NAME
```

Перед массовым удалением сделай backup.

## Backup

Через Mirage Admin можно создать, скачать, импортировать, удалить и восстановить
backup.

Через CLI:

```bash
sudo /usr/local/bin/mirage-xui-backup
ls -lah /home/mirage/mirage-vpn/backups
```

Backup timer:

```bash
systemctl status mirage-xui-backup.timer --no-pager
```

Подробная процедура:
[Бэкапы и восстановление](runbooks/backup-xui.md).

## Restore

Restore через Mirage Admin создаёт заявку. Root-helper проверяет backup, делает
pre-restore backup, останавливает `x-ui`, заменяет базу и запускает сервис.

Restore временно прерывает VPN. На рабочем сервере делай его только в окно
обслуживания.

Проверить helper:

```bash
systemctl status mirage-admin-restore.path --no-pager
```

## Пересоздать VPN inbound

Пересоздавай inbound, если меняешь Reality target/SNI, public host, ключи
Reality или исправляешь ошибочную ручную настройку.

Перед reset:

```bash
sudo /usr/local/bin/mirage-xui-backup
```

Reset:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops bootstrap-vpn \
  --reset-inbound \
  --reality-target www.amazon.com:443 \
  --reality-sni www.amazon.com \
  --print-links
```

После reset выдай свежие ссылки и удали старые профили из клиентских приложений.

## Telegram alerts

Alerts выключены по умолчанию. Чтобы включить уведомления, задай в
`ops/admin/.env.local`:

```env
MIRAGE_ALERTS_ENABLED=true
MIRAGE_ALERT_TELEGRAM_BOT_TOKEN=PASTE_BOT_TOKEN
MIRAGE_ALERT_TELEGRAM_CHAT_ID=PASTE_CHAT_ID
```

Затем перезапусти Admin:

```bash
sudo docker compose --env-file ops/admin/.env.local -f ops/admin/compose.yml up -d --build
```

Тестовое уведомление можно отправить из Mirage Admin.

## Диагностика

### Клиент показывает `unknown IP`

Проверь public host:

```bash
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops public-host
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops vpn-diagnose
```

Если host неверный, задай `MIRAGE_XUI_PUBLIC_HOST` в `ops/xui/.env.local` и
пересоздай inbound.

### Клиент зависает на timeout

Проверь порт, firewall и сервис:

```bash
sudo ss -tlnp | grep ':443'
sudo ufw status numbered
systemctl status x-ui --no-pager
sudo journalctl -u x-ui -n 100 --no-pager
```

Если `443/tcp` доступен, но подключение не идёт, проверь `vpn-diagnose`: Reality
target, SNI, ключи, short IDs и клиенты должны быть заполнены.

### Mirage Admin не открывается

Проверь контейнер и локальный порт:

```bash
sudo docker compose --env-file ops/admin/.env.local -f ops/admin/compose.yml ps
sudo ss -tlnp | grep '127.0.0.1:8090'
curl -fsS http://127.0.0.1:8090/healthz
```

Если снаружи открывается `8090`, закрой порт в firewall. Mirage Admin должен
быть доступен только через SSH-туннель.

### 3x-ui не открывается через туннель

Проверь сервис и порт панели:

```bash
systemctl status x-ui --no-pager
sudo /usr/local/x-ui/x-ui setting -show true
sudo ss -tlnp | grep 'ПОРТ_ПАНЕЛИ'
```

Если сервис остановлен:

```bash
sudo systemctl start x-ui
```

## Чек-лист операции

- [ ] Перед рискованным изменением сделан backup.
- [ ] Админка и 3x-ui доступны только через SSH-туннель.
- [ ] `vpn-diagnose` не показывает предупреждений.
- [ ] `ufw` открывает только нужные публичные порты.
- [ ] У постоянных участников отдельные профили.
- [ ] Новые ссылки сохранены вне git.
- [ ] После reset старые профили удалены из клиентских приложений.
