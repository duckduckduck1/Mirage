# Mirage

[![standard-readme compliant](https://img.shields.io/badge/readme%20style-standard-brightgreen.svg?style=flat-square)](https://github.com/RichardLitt/standard-readme)
[![Лицензия: MIT](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square)](LICENSE)

Разворачивает управляемый VPN-сервер (VLESS Reality) на свежем VPS одной командой.

Mirage превращает чистый VPS в управляемый VPN-сервер: поднимает Xray/3x-ui с
VLESS Reality на `443/tcp`, создаёт профили доступа, локальную админ-панель и
бэкапы. Конфигурация, профили и команды развёртывания живут в одном
репозитории, а рабочие секреты остаются вне git — поэтому сервер можно быстро
пересоздать на новом VPS.

## Содержание

- [Безопасность](#безопасность)
- [О проекте](#о-проекте)
- [Установка](#установка)
- [Эксплуатация](#эксплуатация)
- [Диагностика](#диагностика)
- [Документация](#документация)
- [Структура репозитория](#структура-репозитория)
- [Вклад](#вклад)
- [Лицензия](#лицензия)

## Безопасность

Mirage управляет VPN-сервером и его секретами, поэтому обращайся с репозиторием и
файлом доступа аккуратно.

- Панель 3x-ui и Mirage Admin **не открываются наружу** — только через SSH-туннель.
- `access.md` содержит токены, пароли и параметры доступа. Это секретный файл: не
  отправляй его в чат, issue или pull request и не добавляй в git.

Никогда не коммить в git:

- `.env.local`, `users.local.json`, backup-файлы и дампы базы;
- `access.md`, клиентские и subscription-ссылки;
- UUID, Reality private key, short ID;
- пароль панели, API-токен, `WEB_BASE_PATH`;
- реальные IP и домены, раскрывающие рабочую инфраструктуру.

Храни секреты и бэкапы в менеджере паролей или другом защищённом хранилище.

## О проекте

Mirage поднимает VLESS Reality — протокол, который маскирует VPN-трафик под
обычный TLS к популярному сайту (по умолчанию `www.amazon.com`), что затрудняет
блокировку. Стек разворачивается на свежем VPS с Ubuntu 24.04 и управляется из
одного репозитория, поэтому миграция на новый сервер занимает минуты.

Возможности:

- безопасный bootstrap VPS через Ansible;
- установка Docker, 3x-ui/Xray и Mirage Admin одной командой;
- VLESS Reality на `443/tcp`;
- фиксированная версия Xray, совместимая с sing-box/Hiddify;
- авто-освобождение портов `80/443` от чужого веб-сервера (nginx хостера);
- профили `main`, `partner`, `shared` и возможность создавать новые;
- Mirage Admin на `127.0.0.1:8090`, панель 3x-ui — только через SSH-туннель;
- Telegram-алерты;
- автоматические и ручные бэкапы базы 3x-ui, импорт и восстановление.

Как устроен стек — в [docs/architecture.md](docs/architecture.md).

## Установка

Нужен свежий VPS на Ubuntu 24.04 и SSH-доступ. Полный путь, включая первичный
bootstrap через Ansible, описан в [руководстве](docs/guide.md).

Короткая версия для уже подготовленного VPS:

```bash
cd /home/mirage/projects/Mirage
git switch dev
git pull --ff-only origin dev
sudo bash ops/vpn/deploy.sh SERVER_HOST_OR_DOMAIN
```

В конце deploy напечатает основные пути. Сразу сохрани файл доступа:

```bash
sudo cat /home/mirage/mirage-vpn/access.md
```

Проверь, что сервер поднялся:

```bash
sudo -E bash ops/release/check-local.sh
sudo ss -tlnp | grep ':443'      # на 443 должен слушать xray
sudo ufw status numbered
```

Ожидаемо: `443/tcp` открыт снаружи, а порты панели 3x-ui и Mirage Admin закрыты —
они доступны только через SSH-туннель.

## Эксплуатация

Все процедуры с командами — в [руководстве](docs/guide.md). Коротко:

- **VPN-профили** лежат на VPS в `/home/mirage/mirage-vpn/links/`. Выдать новый:

  ```bash
  sudo docker compose -f ops/xui/compose.yml run --rm xui-ops \
    ensure-client --email CLIENT_NAME --print-links
  ```

  Используй технические имена (`phone`, `tablet`, `friend-a`), не личные данные.
- **Mirage Admin** — токены, alerts и восстановление бэкапов; открывается через
  SSH-туннель на `127.0.0.1:8090`
  ([как открыть](docs/guide.md#5-открой-mirage-admin)).
- **Бэкапы** базы 3x-ui идут по таймеру и вручную:

  ```bash
  sudo /usr/local/bin/mirage-xui-backup
  ```

- **Telegram-алерты** включаются в `ops/admin/.env.local`
  ([инструкция](docs/guide.md#7-включи-telegram-alerts)).

## Диагностика

Частые проблемы при подключении (подробно — в
[руководстве](docs/guide.md#диагностика)):

- **Клиент виснет на `timeout`, хотя `443/tcp` открыт.** Порт 443 занял чужой
  сервис (обычно предустановленный nginx хостера) — Xray не поднялся. `deploy.sh`
  сам гасит такие сервисы; вручную:
  `sudo systemctl disable --now nginx && sudo systemctl restart x-ui`.
- **Hiddify пишет `timeout` / `reality verification failed`, а v2rayN/v2rayNG
  работают.** Несовместимость версий REALITY: установщик 3x-ui тянет самый свежий
  Xray, а ядро Hiddify (sing-box) его вариант не поддерживает. `deploy.sh` пинит
  совместимую версию (`MIRAGE_XRAY_VERSION`, сейчас `v25.12.8`).

## Документация

- [Руководство](docs/guide.md) — установка, настройка, обслуживание и восстановление.
- [Архитектура](docs/architecture.md) — как устроен стек.
- [Mirage Admin](ops/admin/README.md) — справочник панели и API.
- [xui-ops](ops/xui/README.md) — справочник CLI управления 3x-ui.

## Структура репозитория

| Путь | Назначение |
|---|---|
| `ops/vpn` | однокомандный deploy |
| `ops/admin` | локальная админ-панель, alerts и бэкапы |
| `ops/xui` | управление 3x-ui через API |
| `infra/ansible` | первичный bootstrap VPS |
| `docs` | руководство и архитектура |

## Вклад

Баги и предложения — через issues. Правила по веткам, коммитам и pull request'ам
описаны в [CONTRIBUTING.md](CONTRIBUTING.md).

Pull request'ы приветствуются. Не добавляй в коммиты секреты и реальные параметры
инфраструктуры (см. [Безопасность](#безопасность)).

## Лицензия

[MIT](LICENSE) © Richard.
