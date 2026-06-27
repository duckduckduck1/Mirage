# Mirage

> Самостоятельно управляемый VPN + Telegram-прокси с маскировкой трафика,
> подписками и быстрым переносом между VPS.

**Статус:** 🚧 активная разработка. Готовы безопасный Ansible-bootstrap VPS и
ручная настройка 3x-ui/Xray с VLESS Reality на `443/tcp`. Панель 3x-ui закрыта
за SSH-туннелем. Следующие этапы — Shadowsocks-2022, Telegram-прокси `mtg`,
бэкапы, домен для подписок и автоматизация сервисов через Ansible.

## Что это

Mirage — это инфраструктурный проект для управляемого доступа через арендованный
VPS:

- **VPN** — Xray-core (VLESS + Reality + XTLS-Vision) под панелью 3x-ui.
  Соединение для систем фильтрации (DPI) неотличимо от обычного захода на
  разрешённый сайт.
- **Telegram-прокси** — `mtg` (MTProto, режим FakeTLS) с маскировкой под
  выбранный разрешённый домен.

В резерве — Shadowsocks-2022 на случай блокировки основного протокола.

## Ключевая идея: IP как расходник

Блокировки происходят регулярно, поэтому проект спроектирован так, чтобы **смена
сервера или IP не требовала ручной перенастройки клиентов**:

- раздаём **subscription-ссылки** как единый источник правды, а не отдельные
  конфиги для каждого клиента;
- адрес подписки привязан к **домену**, а не к IP;
- базовый доступ и защита сервера уже кодифицированы в **Ansible**; установка
  3x-ui/Xray пока зафиксирована runbook'ом и будет автоматизироваться позже;
- база панели и конфиги должны попадать в регулярный бэкап.

Подробнее — в [документации по архитектуре](docs/architecture.md).

## Стек

| Слой | Технологии |
|---|---|
| Сервер | Ubuntu/Debian VPS, `systemd`, `ufw`, `fail2ban` |
| VPN | Xray-core (VLESS + Reality + Vision), панель 3x-ui, Shadowsocks-2022 (резерв) |
| Telegram | `mtg` (MTProto FakeTLS) в Docker |
| Инфраструктура | Ansible-bootstrap (готово), 3x-ui runbook (готово), Terraform и Docker Compose (план) |
| Наблюдаемость (план) | Prometheus, Grafana, Alertmanager |

## Структура репозитория

```
.
├── README.md            — этот файл
├── CONTRIBUTING.md      — правила веток, коммитов и PR
├── docs/
│   ├── setup.md         — установка и первичная настройка
│   ├── architecture.md  — архитектура и дизайн миграции
│   ├── style-guide.md   — стиль документации (на базе Google dev docs style)
│   ├── adr/             — Architecture Decision Records (журнал решений)
│   └── runbooks/        — эксплуатационные инструкции
├── infra/
│   └── ansible/         — первый bootstrap VPS и базовая защита
└── .github/             — шаблоны PR и задач
```

## Документация

- [Архитектура](docs/architecture.md)
- [Установка Mirage](docs/setup.md)
- [Как контрибьютить (ветки, коммиты, PR)](CONTRIBUTING.md)
- [Стиль документации](docs/style-guide.md)
- [Журнал архитектурных решений (ADR)](docs/adr/)
- [Runbook: bootstrap VPS через Ansible](docs/runbooks/bootstrap-vps-ansible.md)
- [Runbook: ручная настройка 3x-ui и VLESS Reality](docs/runbooks/setup-xui-vless-reality.md)
- [Runbook: миграция на новый VPS](docs/runbooks/migrate-vps.md)

## Лицензия

[MIT](LICENSE).

Используй проект ответственно и учитывай требования своей юрисдикции.
