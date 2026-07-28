# Чистый VPS

Этот сценарий предназначен только для нового Ubuntu 22.04 без Docker, контейнеров
и данных Docker. Роль `docker_engine` ставит Docker Engine и Compose plugin из
официального APT-репозитория Docker; если Docker или его данные уже существуют,
она останавливается без изменений.

1. Под root установите Ansible и Git, затем получите ветку `dev` или принятый
   релиз Mirage.
2. Перейдите в `infra/ansible`, создайте игнорируемый `group_vars/all.yml` на
   основе `group_vars/all.example.yml` и поместите секреты в root-only файлы вне
   checkout.
3. Укажите утверждённые параметры и включите нужные роли Marzban, Xray,
   сертификата, инбаундов, Caddy и Telegram-бота. Не придумывайте параметры:
   сверяйтесь с [документацией Marzban](https://gozargah.github.io/marzban/ru/docs/introduction).
4. Выполните проверку синтаксиса, затем сценарий:

```bash
ansible-playbook --syntax-check -i inventory/localhost.yml playbooks/deploy-clean.yml
ansible-playbook -i inventory/localhost.yml playbooks/deploy-clean.yml
```

5. Создайте администратора Marzban штатной CLI, проверьте панель, HTTPS-подписку,
бота и поддерживаемые клиентские профили.

Не запускайте этот playbook на общем или уже настроенном VPS: используйте
[сценарий подготовленного VPS](/deployment/prepared-vps).
