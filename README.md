# Mirage

Mirage — управляемый VPN-стек для VPS. Проект разворачивает Xray/3x-ui,
создаёт VLESS Reality на `443/tcp`, выдаёт клиентские профили и поднимает
локальную админ-панель для операций: профили, ссылки, бэкапы, восстановление и
проверка состояния.

Главная идея: сервер можно заменить быстро. IP считается расходником, а
конфигурация, профили и бэкапы остаются управляемыми.

## Что готово в v0.1

- Bootstrap свежего VPS через Ansible: пользователь `mirage`, SSH по ключу,
  `ufw`, `fail2ban`, SSH-hardening.
- Однокомандный deploy через `ops/vpn/deploy.sh`.
- 3x-ui/Xray с VLESS Reality на `443/tcp`.
- Базовые профили `main`, `partner`, `shared`.
- Mirage Admin на `127.0.0.1:8090`, без публичного доступа.
- 3x-ui панель на `127.0.0.1:ПОРТ_ПАНЕЛИ`, без публичного доступа.
- Ежедневные бэкапы базы 3x-ui, импорт и restore-helper.
- Release gate для проверки перед выпуском.

## Быстрый старт

На свежем VPS сначала выполни bootstrap из
[гайда развёртывания](docs/deploy.md), затем запусти deploy:

```bash
cd /home/mirage/projects/Mirage
git switch dev
git pull --ff-only origin dev
sudo bash ops/vpn/deploy.sh SERVER_HOST_OR_DOMAIN
```

После завершения скрипт покажет:

```text
Access file: /home/mirage/mirage-vpn/access.md
Links directory: /home/mirage/mirage-vpn/links
Backup directory: /home/mirage/mirage-vpn/backups
```

Файл `access.md` содержит локальные URL, команды SSH-туннелей, token админки и
пути к файлам профилей. Это секретный файл: не отправляй его в чат, issue, PR и
не добавляй в git.

## Проверка после deploy

На VPS:

```bash
sudo -E bash ops/release/check-local.sh
sudo ss -tlnp | grep -E ':443|127.0.0.1:8090'
sudo ufw status numbered
```

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

Ожидаемо: `443` доступен, `8090` и порт панели 3x-ui недоступны снаружи.

## Документация

- [Развёртывание на VPS](docs/deploy.md)
- [Эксплуатация](docs/operations.md)
- [Release-check v0.1](docs/release-v0.1.md)
- [Архитектура](docs/architecture.md)
- [Bootstrap VPS через Ansible](docs/runbooks/bootstrap-vps-ansible.md)
- [Бэкапы и восстановление](docs/runbooks/backup-xui.md)
- [Миграция на новый VPS](docs/runbooks/migrate-vps.md)
- [Справочник xui-ops](ops/xui/README.md)
- [Справочник Mirage Admin](ops/admin/README.md)

## Безопасность секретов

Не добавляй в git:

- `.env.local`, `users.local.json`, backup-файлы и дампы базы;
- `access.md`, клиентские ссылки, subscription-ссылки;
- UUID, Reality private key, short IDs;
- пароль панели, API token, `WEB_BASE_PATH`;
- реальные IP и домены, если они раскрывают рабочую инфраструктуру.

Храни секреты в менеджере паролей. Директории `backups/`, `exports/`,
`secrets/`, локальные env-файлы и локальные списки пользователей уже исключены
из git.

## Состав репозитория

| Путь | Назначение |
|---|---|
| `ops/vpn` | однокомандный deploy |
| `ops/admin` | локальная админ-панель, API, alerts, backup lifecycle |
| `ops/xui` | CLI для управления 3x-ui через API |
| `infra/ansible` | первый bootstrap VPS |
| `docs` | релизная документация |

## Лицензия

[MIT](LICENSE).
