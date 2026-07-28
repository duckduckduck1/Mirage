# Ansible-инфраструктура Mirage 2.0

Playbook’и запускаются **локально на целевом VPS** из root-сеанса. Они не
подключаются к удалённым хостам и не содержат рабочие секреты.

## Подготовка checkout

На VPS установите Ansible и Git, получите принятую ветку и перейдите в этот
каталог. Для разработки используется `dev`; для эксплуатации после выпуска —
принятый `main` или конкретный релизный тег.

Создайте `group_vars/all.yml` на основе `group_vars/all.example.yml`. Этот файл
игнорируется Git. Укажите в нём только пути к root-only секретам; сами токены,
пароли, ключи, сертификаты и архивы хранятся за пределами checkout.

Перед запуском любого сценария:

```bash
ansible-playbook --syntax-check -i inventory/localhost.yml site.yml
```

## Сценарии

### Чистый VPS

Только новый Ubuntu 22.04 без Docker и `/var/lib/docker`. Роль Docker использует
официальный APT-репозиторий Docker и откажется менять существующую установку.

```bash
ansible-playbook -i inventory/localhost.yml playbooks/deploy-clean.yml
```

### Подготовленный VPS

Docker Compose уже существует и был отдельно принят владельцем. Playbook лишь
проверяет `docker compose version`, не обновляет Docker и не затрагивает чужие
Docker-объекты.

```bash
ansible-playbook -i inventory/localhost.yml playbooks/deploy-prepared.yml
```

### Восстановление

Сначала разверните базовую инфраструктуру, затем передайте абсолютный путь к
штатному root-owned SQLite-архиву Marzban вне checkout:

```bash
ansible-playbook -i inventory/localhost.yml playbooks/restore.yml \
  -e 'marzban_restore_archive=/root/restore/marzban-backup.tar.gz'
```

Сценарий допускает только пути `/opt/marzban` и `/var/lib/marzban` внутри
архива, повторно применяет инфраструктурные роли и обязательно выполняет
`marzban restart` после распаковки.

## После применения

Создайте администратора через штатный Marzban CLI и фактически проверьте
панель, Telegram-бот, HTTPS-подписку, резервное копирование и поддерживаемые
клиенты. Полный порядок и ограничения находятся в публичной документации
Mirage и во внешнем `PLAN.md`.
