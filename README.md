# Mirage

Mirage — репозиторий для развёртывания и эксплуатации собственного VPN/прокси
стека на VPS. Цель проекта — быстро поднимать рабочий сервер, управлять доступом
через 3x-ui API, выпускать отдельные профили для участников и сохранять
возможность переезда на новый VPS при блокировке IP.

## Текущий статус

Готов и проверен VPN-этап:

- базовый bootstrap VPS через Ansible: пользователь `mirage`, SSH по ключу,
  `sudo`, `ufw`, `fail2ban`, SSH-hardening;
- 3x-ui/Xray на VPS;
- VLESS Reality на `443/tcp`;
- панель 3x-ui закрыта на `127.0.0.1` и открывается только через SSH-туннель;
- `xui-ops` управляет 3x-ui через API из Docker-контейнера;
- автоматизировано создание inbound и профилей `main`, `partner`, `shared`;
- добавлены команды диагностики, бэкапа и безопасного пересоздания VPN inbound;
- добавлена локальная Mirage Admin-панель для профилей, бэкапов, restore и alerts.

Следующий крупный этап — Telegram MTProxy/FakeTLS. Он будет оформлен отдельным
гайдом после реализации.

## Что входит в проект

| Часть | Назначение |
|---|---|
| `infra/ansible` | Первый bootstrap свежего VPS и базовая защита |
| `ops/vpn` | Однокомандный deploy VPN, админки, бэкапов и restore helper |
| `ops/xui` | CLI и Docker-обёртка для управления 3x-ui через API |
| `ops/admin` | Локальная админ-панель, API, backup lifecycle, restore и alerts |
| `docs/setup` | Пошаговое развёртывание VPN на VPS |
| `docs/operations` | Работа с уже поднятым VPN: ссылки, клиенты, бэкапы, диагностика |
| `docs/runbooks` | Детальные процедуры для отдельных операций |
| `docs/adr` | Архитектурные решения |

## Основная идея

IP сервера считается расходником. Если VPS попал под блокировку, проект должен
позволять быстро поднять новый сервер, восстановить конфигурацию и перевести
клиентов без ручной пересборки каждого профиля.

Для этого Mirage использует:

- воспроизводимый bootstrap сервера;
- 3x-ui как панель управления клиентами и подписками;
- `xui-ops` как автоматизированный слой поверх API панели;
- отдельные клиентские профили по ролям: `main`, `partner`, `shared`;
- бэкапы базы 3x-ui;
- домен и subscription-ссылки как следующий шаг для более удобной миграции.

Reality target/SNI маскирует TLS-профиль соединения, но не защищает сам IP от
блокировки. Поэтому документация отдельно описывает бэкапы, миграцию и будущую
модель с доменом.

## Быстрый старт по документации

1. Разверни VPN на новом VPS:
   [docs/setup/README.md](docs/setup/README.md).
2. Работай с поднятым сервисом:
   [docs/operations/README.md](docs/operations/README.md).
3. Посмотри архитектурную модель:
   [docs/architecture.md](docs/architecture.md).
4. Перед релизом v0.1 пройди smoke-check:
   [docs/runbooks/release-v0-1-smoke.md](docs/runbooks/release-v0-1-smoke.md).
5. Перед изменениями делай бэкап:
   [docs/runbooks/backup-xui.md](docs/runbooks/backup-xui.md).
6. Для переезда на новый VPS используй:
   [docs/runbooks/migrate-vps.md](docs/runbooks/migrate-vps.md).

## Безопасность секретов

Не добавляй в git:

- реальные IP и домены;
- `vless://`, `ss://` и subscription-ссылки;
- UUID клиентов, short IDs, Reality private key;
- пароль панели, API token, `WEB_BASE_PATH`;
- `.env.local`, `users.local.json`, backup-файлы и дампы базы.

Локальные секреты храни в менеджере паролей. Папка `backups/` и локальные файлы
`ops/xui/*.local.json`, `ops/xui/.env.local` игнорируются git.

## Документация

- [Установка VPN на VPS](docs/setup/README.md)
- [Эксплуатация VPN](docs/operations/README.md)
- [Smoke-check v0.1](docs/runbooks/release-v0-1-smoke.md)
- [Архитектура](docs/architecture.md)
- [Технический справочник xui-ops](ops/xui/README.md)
- [Технический справочник Mirage Admin](ops/admin/README.md)
- [Bootstrap VPS через Ansible](docs/runbooks/bootstrap-vps-ansible.md)
- [Бэкап 3x-ui](docs/runbooks/backup-xui.md)
- [Миграция на новый VPS](docs/runbooks/migrate-vps.md)
- [Домен и subscription-ссылки](docs/runbooks/domain-and-subscriptions.md)
- [Production-checkpoint VLESS Reality](docs/runbooks/vless-production-checkpoint.md)
- [Fallback: ручная настройка 3x-ui](docs/runbooks/setup-xui-vless-reality.md)
- [Fallback: проверка Shadowsocks-2022](docs/runbooks/setup-shadowsocks-2022.md)
- [Правила работы с проектом](CONTRIBUTING.md)
- [Стиль документации](docs/style-guide.md)

## Лицензия

[MIT](LICENSE).
