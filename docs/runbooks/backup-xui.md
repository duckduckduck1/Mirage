# Бэкап 3x-ui

Runbook описывает первый ручной бэкап 3x-ui и правила хранения backup-файлов.
Бэкап нужен до ротации секретов, добавления Shadowsocks и любого переезда на
новый VPS.

Не добавляй backup-файлы, дампы базы, `x-ui.db`, DSN, пароли, UUID, `vless://`
ссылки, приватные ключи Reality и Telegram bot token в git.

## Что входит в бэкап

Минимальный backup-набор:

- база 3x-ui: клиенты, inbound'ы, UUID, лимиты, Reality-параметры, short IDs;
- настройки панели: порт панели, `WEB_BASE_PATH`, subscription URI path;
- сведения о домене: `vpn.ДОМЕН`, `sub.ДОМЕН`, TTL и DNS-провайдер;
- список открытых портов: `22/tcp`, `443/tcp`, `8388/tcp`, будущий порт подписки;
- версия 3x-ui и Xray;
- дата проверки восстановления.

Храни секретные значения в менеджере паролей. Backup-файл храни отдельно от git:
локально в защищённой папке, в зашифрованном облаке или в password manager,
который умеет файлы.

## Имена файлов

Используй понятные имена без реального IP:

```text
mirage-xui-YYYYMMDD-HHMM.db
mirage-xui-YYYYMMDD-HHMM.dump
mirage-xui-YYYYMMDD-HHMM.notes.md
```

Пример:

```text
mirage-xui-20260628-2130.db
```

Не добавляй в имя файла домен, IP или имя провайдера.

## Быстрый бэкап через панель

1. Открой SSH-туннель к панели:

   ```powershell
   ssh -N -i $HOME\.ssh\mirage_ed25519 -L 2096:127.0.0.1:ПОРТ_ПАНЕЛИ mirage@SERVER_IP
   ```

2. Открой:

   ```text
   http://localhost:2096/WEB_BASE_PATH
   ```

3. Войди в 3x-ui.
4. Открой **Бэкап и восстановление**.
5. Нажми **Экспорт**, **Backup** или кнопку с похожим названием.
6. Сохрани файл вне репозитория.
7. Переименуй файл по схеме:

   ```text
   mirage-xui-YYYYMMDD-HHMM.db
   ```

8. Сохрани рядом отдельную заметку `mirage-xui-YYYYMMDD-HHMM.notes.md` вне git.

Минимальная заметка:

```text
Дата:
3x-ui version:
Xray version:
Панель: 127.0.0.1:ПОРТ_ПАНЕЛИ
VPN-домен: vpn.ДОМЕН
Subscription-домен: sub.ДОМЕН
Inbound: VLESS Reality :443
Inbound: Shadowsocks :8388
Проверка восстановления:
```

## Ручной бэкап SQLite

Если 3x-ui использует SQLite, база по умолчанию лежит в `/etc/x-ui`. Проверь путь:

```bash
sudo ls -la /etc/x-ui
```

Сделай копию на VPS:

```bash
sudo install -d -m 700 /home/mirage/backups/x-ui
sudo cp -a /etc/x-ui/x-ui.db /home/mirage/backups/x-ui/mirage-xui-YYYYMMDD-HHMM.db
sudo chown mirage:mirage /home/mirage/backups/x-ui/mirage-xui-YYYYMMDD-HHMM.db
```

Скачай файл на локальную машину:

```powershell
scp -i $HOME\.ssh\mirage_ed25519 mirage@SERVER_IP:/home/mirage/backups/x-ui/mirage-xui-YYYYMMDD-HHMM.db BACKUP_LOCAL_DIR\
```

После скачивания проверь, что backup-файл лежит вне репозитория Mirage.

## Ручной бэкап PostgreSQL

Если 3x-ui использует PostgreSQL, не копируй DSN в документацию. Возьми DSN из
защищённого места на сервере или из менеджера паролей и выполни дамп:

```bash
pg_dump "XUI_DB_DSN" --format=custom --file=/home/mirage/backups/x-ui/mirage-xui-YYYYMMDD-HHMM.dump
```

Ограничь доступ к файлу:

```bash
chmod 600 /home/mirage/backups/x-ui/mirage-xui-YYYYMMDD-HHMM.dump
```

Скачай дамп локально:

```powershell
scp -i $HOME\.ssh\mirage_ed25519 mirage@SERVER_IP:/home/mirage/backups/x-ui/mirage-xui-YYYYMMDD-HHMM.dump BACKUP_LOCAL_DIR\
```

## Автоматический бэкап через Telegram bot

3x-ui умеет отправлять database backup через Telegram bot. Используй это как
дополнительный канал, а не единственную копию.

В панели открой **Настройки панели** → **Telegram Bot** и настрой:

- **Telegram Bot Token**;
- **Admin Chat ID(s)**;
- **Notification Time**;
- **Database Backup**;
- **Login Notification**.

Храни bot token как секрет. Не добавляй его в git и не публикуй в PR.

## Проверка backup-файла

После создания бэкапа проверь:

```bash
ls -lh /home/mirage/backups/x-ui
file /home/mirage/backups/x-ui/mirage-xui-YYYYMMDD-HHMM.db
```

Для SQLite можно дополнительно проверить базу:

```bash
sqlite3 /home/mirage/backups/x-ui/mirage-xui-YYYYMMDD-HHMM.db 'PRAGMA integrity_check;'
```

Ожидаемый результат:

```text
ok
```

Если `sqlite3` не установлен:

```bash
sudo apt update
sudo apt install -y sqlite3
```

## Проверка восстановления

Не считай бэкап рабочим, пока не проверен сценарий восстановления. Для первого
полного теста используй новый VPS или временную тестовую машину:

1. Подними базовую защиту через Ansible.
2. Установи 3x-ui той же или совместимой версии.
3. Останови `x-ui`.
4. Восстанови базу или дамп.
5. Запусти `x-ui`.
6. Проверь панель, inbound'ы, клиентов и порты.
7. Подключи тестовый клиент.

Восстановление на боевом сервере делай только после отдельного свежего бэкапа.

## Ротация после утечки

Если клиентская ссылка, UUID, пароль панели, API token или приватный ключ Reality
попали во внешний канал, выполни ротацию:

1. Сделай свежий бэкап.
2. Смени пароль панели.
3. Смени API token, если он включён.
4. Пересоздай клиента или обнови UUID.
5. Перегенерируй Reality keypair, если был раскрыт приватный ключ.
6. Экспортируй новые ссылки.
7. Проверь подключение.
8. Удали старые профили у клиентов.
9. Сделай новый бэкап после ротации.

## Чек-лист

- [ ] Бэкап создан до добавления новых inbound'ов.
- [ ] Backup-файл лежит вне git.
- [ ] Пароль панели, `WEB_BASE_PATH`, API token и DSN сохранены в менеджере
  паролей.
- [ ] Проверена целостность SQLite или успешность `pg_dump`.
- [ ] Описан способ восстановления.
- [ ] После ротации создан новый backup-файл.

## Справка

- [3x-ui: параметры базы данных](https://github.com/MHSanaei/3x-ui/wiki/Configuration)
- [3x-ui: Telegram bot и database backup](https://github.com/MHSanaei/3x-ui/wiki/Advanced)
