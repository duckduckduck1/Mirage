# Mirage

Mirage — воспроизводимая инфраструктура VPN на основе штатного Marzban,
закреплённого Xray-core и одной HTTPS-подписки для каждого пользователя.

## Mirage 2.0

- Marzban управляет пользователями, подписками, Telegram-ботом и резервными
  копиями без собственной API-обвязки;
- поддерживаемые клиенты MVP: Hiddify и Karing для VLESS TCP REALITY, VLESS
  gRPC REALITY и Trojan TLS;
- XHTTP REALITY сохраняется в общей подписке для совместимых Xray-клиентов, но
  не заявляется поддерживаемым в Hiddify и Karing;
- инфраструктура рассчитана на Ubuntu 22.04 LTS и запускается локально на VPS
  через Ansible.

Полная русская документация публикуется на
[GitHub Pages](https://duckduckduck1.github.io/Mirage/). Английская версия
расположена по адресу `/en/` этого сайта.

## Начало работы

Выберите один из документированных сценариев:

1. [Чистый VPS](https://duckduckduck1.github.io/Mirage/deployment/clean-vps)
   — Docker и Mirage устанавливаются с нуля.
2. [Подготовленный VPS](https://duckduckduck1.github.io/Mirage/deployment/prepared-vps)
   — Docker уже установлен и не изменяется автоматизацией.
3. [Восстановление](https://duckduckduck1.github.io/Mirage/deployment/restore)
   — развёртывание штатного архива Marzban на подготовленном сервере.

Не коммитьте IP-адреса, домены, токены, ключи, резервные архивы, UUID и ссылки
подписок. Перед эксплуатационными действиями прочитайте [политику
безопасности](https://duckduckduck1.github.io/Mirage/reference/security).

## Разработка

`dev` — интеграционная ветка, `main` содержит только принятые релизы. Перед
pull request запускайте:

```bash
bash ops/release/check-local.sh
```

Подробный порядок — в [CONTRIBUTING.md](CONTRIBUTING.md). Лицензия проекта —
[MIT](LICENSE).
