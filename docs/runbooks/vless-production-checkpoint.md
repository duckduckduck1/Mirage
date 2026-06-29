# Production-checkpoint VLESS Reality

Runbook фиксирует рабочее состояние Mirage после настройки 3x-ui и `xui-ops`.
На этом этапе production-схема использует только `VLESS Reality` на `443/tcp`.
Резервные протоколы и публичные subscription-ссылки добавляются отдельными
этапами после проверки.

Не добавляй в git реальные IP, `vless://`-ссылки, UUID, пароли, приватные ключи
Reality, `WEB_BASE_PATH`, subscription path и backup-файлы.

## Целевое состояние

```text
VPS
  ├─ 22/tcp              SSH по ключу
  ├─ 443/tcp             Xray VLESS Reality
  ├─ 127.0.0.1:ПОРТ_ПАНЕЛИ  3x-ui через SSH-туннель
  └─ 8388/tcp            закрыт, Shadowsocks не используется
```

3x-ui остаётся доступной только через SSH-туннель. Панель может показывать
предупреждение про HTTP, но оно не критично, пока панель слушает только
`127.0.0.1` и порт панели не открыт в `ufw`.

## Проверка портов

На VPS выполни:

```bash
cd /home/mirage/projects/Mirage
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops vpn-diagnose
sudo ss -tlnp | grep -E ':443|:8388|:ПОРТ_ПАНЕЛИ'
sudo ufw status numbered
systemctl status x-ui --no-pager
```

Ожидаемые признаки:

```text
warnings: none
127.0.0.1:ПОРТ_ПАНЕЛИ     x-ui
*:443                     xray-linux-amd64
```

В `ufw` должны быть открыты только рабочие публичные порты:

```text
22/tcp                    ALLOW IN
443/tcp                   ALLOW IN
```

Порт `8388/tcp` не должен слушать и не должен быть открыт в `ufw`, пока
Shadowsocks не входит в рабочую схему.

## Проверка панели

С локальной Windows-машины можно открыть кабинет скриптом:

```powershell
.\ops\xui\open-panel.ps1 -ServerHost SERVER_HOST_OR_DOMAIN
```

Или открой SSH-туннель вручную:

```powershell
ssh -N -i $HOME\.ssh\mirage_ed25519 -L 2096:127.0.0.1:ПОРТ_ПАНЕЛИ mirage@SERVER_HOST_OR_DOMAIN
```

Открой панель:

```text
http://localhost:2096/WEB_BASE_PATH
```

Проверь:

- вход работает с новым паролем;
- `WEB_BASE_PATH` сохранён в менеджере паролей;
- subscription path не равен `/sub/`;
- новый subscription path сохранён в менеджере паролей;
- порт панели не открыт наружу.

## Проверка клиента VLESS

На VPS проверь API-состояние:

```bash
cd /home/mirage/projects/Mirage
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops vpn-diagnose
```

В 3x-ui открой **Входящие** → `vless-reality-vision`.

Проверь:

- клиенты `main`, `partner`, `shared` существуют;
- `flow` у активного клиента — `xtls-rprx-vision`;
- inbound включён;
- порт inbound — `443`.

В Hiddify выбери новый VLESS-профиль и проверь реальный трафик. В панели у
`vless-reality-vision` должен расти трафик активного клиента.

## Финальный бэкап

После проверки сделай backup 3x-ui и сохрани его вне git:

```bash
cd /home/mirage/projects/Mirage
mkdir -p backups/x-ui
sudo docker compose -f ops/xui/compose.yml run --rm xui-ops backup-db
```

Для внешней копии используй имя:

```text
BACKUP_LOCAL_DIR\mirage-xui-YYYYMMDD-vless-production-checkpoint.db
```

Локальная папка `backups/` внутри репозитория игнорируется git. Для защиты от
потери данных держи вторую копию вне рабочей папки проекта: внешний диск,
зашифрованное облако или менеджер паролей с поддержкой файлов.

## Что не входит в текущий checkpoint

- Shadowsocks-2022 не используется в production-схеме.
- `8388/tcp` закрыт.
- Домен и публичные subscription-ссылки отложены.
- Telegram-прокси `mtg` отложен.
- Автоматизация установки 3x-ui/Xray через Ansible отложена.

## Чек-лист

- [ ] `ufw` открывает только `22/tcp` и `443/tcp`.
- [ ] `ss` показывает `127.0.0.1:ПОРТ_ПАНЕЛИ`.
- [ ] `ss` показывает `*:443`.
- [ ] `ss` не показывает `:8388`.
- [ ] `vpn-diagnose` не показывает предупреждений.
- [ ] Панель открывается только через SSH-туннель.
- [ ] Пароль панели сменён и сохранён вне git.
- [ ] Subscription path отличается от `/sub/`.
- [ ] Профили `main`, `partner`, `shared` созданы.
- [ ] Активный VLESS-клиент работает.
- [ ] Финальный backup сохранён вне git.
