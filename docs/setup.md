# Установка Mirage

Документ описывает полный путь установки Mirage на новый VPS: базовый bootstrap,
панель 3x-ui/Xray, основной VPN-профиль VLESS Reality, резервный Shadowsocks и
подготовку к Telegram-прокси `mtg`.

Mirage проектируется так, чтобы сервер можно было заменить без ручной
перенастройки клиентов. Для этого используй домен, subscription-ссылки, бэкапы и
повторяемые runbooks.

## Целевая схема

```text
Клиентское приложение
  ├─ обновляет подписку: https://sub.ДОМЕН/...
  ├─ подключается к VPN: vpn.ДОМЕН:443 или SERVER_IP:443
  └─ переключается на резерв: Shadowsocks :8388

VPS
  ├─ 22/tcp      SSH
  ├─ 443/tcp     Xray VLESS Reality
  ├─ 8388/tcp    Shadowsocks-2022
  ├─ 8443/tcp    mtg MTProto FakeTLS (план)
  └─ localhost   3x-ui через SSH-туннель
```

## Что подготовить

- VPS с Ubuntu 24.04 LTS или совместимой Ubuntu/Debian-системой.
- Root-доступ для первого входа.
- Локальный SSH-ключ `mirage_ed25519`.
- Домен с управляемым DNS. Домен не скрывает IP от блокировки, но даёт стабильные
  subscription-ссылки и быстрый переезд на новый VPS.
- Менеджер паролей для пароля панели, `WEB_BASE_PATH`, API-токена, ключей и
  бэкапов.

Не добавляй в git реальные IP, пароли, UUID, `vless://`-ссылки, API-токены,
приватные ключи Reality, DSN базы и backup-файлы.

## Шаг 1. Bootstrap VPS через Ansible

Сначала переведи сервер с root-пароля на пользователя `mirage` с SSH-ключом,
`sudo`, `ufw`, `fail2ban` и SSH-hardening.

Выполни runbook:

- [Bootstrap VPS через Ansible](runbooks/bootstrap-vps-ansible.md)

Контрольные проверки:

```bash
sudo -n true
sudo ufw status
sudo /usr/sbin/sshd -T | grep -E 'passwordauthentication|kbdinteractiveauthentication|permitrootlogin|pubkeyauthentication'
```

Ожидаемые признаки:

```text
passwordauthentication no
kbdinteractiveauthentication no
pubkeyauthentication yes
22/tcp ALLOW
443/tcp ALLOW
8388/tcp ALLOW
```

## Шаг 2. Установка 3x-ui и VLESS Reality

Установи 3x-ui и создай основной VPN inbound по runbook:

- [Ручная настройка 3x-ui и VLESS Reality](runbooks/setup-xui-vless-reality.md)

Ключевые требования:

- панель 3x-ui слушает только `127.0.0.1:ПОРТ_ПАНЕЛИ`;
- доступ к панели идёт через SSH-туннель на `localhost:2096`;
- `443/tcp` слушает Xray;
- `ufw` открывает `22/tcp`, `443/tcp`, `8388/tcp`, но не открывает порт панели;
- клиентский профиль содержит публичный адрес сервера или домен.

Проверка на VPS:

```bash
sudo ss -tlnp | grep -E ':443|:ПОРТ_ПАНЕЛИ'
sudo ufw status
systemctl status x-ui --no-pager
```

Проверка с локальной Windows-машины:

```powershell
Test-NetConnection SERVER_IP -Port 443
```

## Шаг 3. Первый бэкап и ротация секретов

После проверки VLESS Reality сделай первый бэкап панели и сохрани его вне git:

- [Бэкап 3x-ui](runbooks/backup-xui.md)

Если в рабочий контекст попадали клиентские ссылки, UUID, пароль панели,
`WEB_BASE_PATH`, API token или приватные ключи Reality, выполни ротацию перед
расширением сервиса. После ротации сделай повторный backup.

## Шаг 4. Резервный Shadowsocks-2022

Shadowsocks нужен как резервный профиль, если блокируют или ломают именно Reality.

Выполни runbook:

- [Резервный Shadowsocks-2022](runbooks/setup-shadowsocks-2022.md)

Ключевые требования:

- отдельный inbound `shadowsocks-2022-reserve`;
- порт `8388/tcp`;
- method `2022-blake3-aes-256-gcm`;
- новый ключ, сохранённый вне git;
- профиль импортируется в Hiddify как одиночная `ss://`-ссылка;
- после проверки сделан новый бэкап 3x-ui.

Проверка:

```bash
sudo ss -tlnp | grep ':8388'
sudo ufw status
```

С локальной Windows-машины:

```powershell
Test-NetConnection SERVER_IP -Port 8388
```

## Шаг 5. Домен и клиентские ссылки

Домен нужен для стабильных ссылок, а не для защиты IP от блокировки. Сначала
переведи VLESS Reality на `vpn.ДОМЕН`, чтобы одиночная клиентская ссылка пережила
смену IP. Публичную subscription-ссылку включай только после первого бэкапа и
проверки TLS-модели.

Выполни runbook:

- [Домен и subscription-ссылки](runbooks/domain-and-subscriptions.md)

Минимальная рабочая схема:

```text
vpn.ДОМЕН   A   SERVER_IP   # адрес подключения клиентов
sub.ДОМЕН   A   SERVER_IP   # будущая публичная подписка
```

Для Cloudflare держи `vpn.ДОМЕН` в режиме **DNS only**. Проксирование Cloudflare
не заменяет TCP-транспорт для Reality и не скрывает VPS от блокировки IP.

## Шаг 6. Telegram-прокси mtg

Целевая схема включает `mtg` в режиме MTProto FakeTLS. Порт `443` уже занят Xray,
поэтому базовый вариант для `mtg` — отдельный порт `8443/tcp`.

До добавления `mtg` нужно выбрать:

- формат запуска: Docker или systemd;
- домен маскировки для FakeTLS;
- схему бэкапа `config.toml` и секретов;
- правило `ufw allow 8443/tcp`.

После реализации добавь отдельный runbook для `mtg` и обнови этот документ.

## Пределы фильтрации

Reality и FakeTLS помогают против обычной фильтрации на уровне протокола и SNI,
но не отменяют блокировку самого IP.

Если оператор включает режим allowlist/drop-all и пропускает только заранее
разрешённые IP-диапазоны, зарубежный VPS не проходит проверку на уровне L3.
Подмена SNI в этом режиме не помогает: IP-проверка срабатывает раньше анализа
домена.

Практические выводы:

- держи IP расходником;
- используй домен и subscription-ссылки для быстрой миграции;
- поддерживай резервный протокол Shadowsocks;
- регулярно делай бэкапы 3x-ui;
- не рассчитывай, что домен сам по себе защитит VPS от IP-блокировки.

## Шаг 7. Бэкап и миграция

Перед миграцией всегда делай свежий бэкап панели и сохраняй его вне git:

- [Бэкап 3x-ui](runbooks/backup-xui.md)

Для переезда используй runbook:

- [Миграция на новый VPS](runbooks/migrate-vps.md)

Минимальная модель переезда:

1. Купить новый VPS.
2. Запустить Ansible-bootstrap.
3. Установить 3x-ui/Xray.
4. Восстановить бэкап панели.
5. Проверить VLESS Reality и Shadowsocks.
6. Переключить DNS A-записи `sub.ДОМЕН` и `vpn.ДОМЕН`.
7. Проверить обновление подписок у клиентов.

## Контрольный чек-лист

- [ ] SSH работает только по ключу.
- [ ] `ufw` активен и открывает только нужные порты.
- [ ] Панель 3x-ui доступна только через SSH-туннель.
- [ ] VLESS Reality работает на `443/tcp`.
- [ ] Shadowsocks работает на `8388/tcp`.
- [ ] В клиентской ссылке указан `vpn.ДОМЕН`, если домен уже настроен.
- [ ] Subscription-ссылка использует `sub.ДОМЕН`, если публичная подписка уже включена.
- [ ] Бэкап 3x-ui сохранён вне git.
- [ ] План миграции проверен по runbook.
