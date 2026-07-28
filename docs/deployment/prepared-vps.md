# Подготовленный VPS

Выберите этот путь, если Docker Compose уже установлен или сервер не является
чистым. Playbook не заменяет Docker и до каких-либо изменений проверяет, что
`docker compose version` доступна.

1. Убедитесь, что Docker и его данные принадлежат области Mirage либо уже
   отдельно приняты владельцем.
2. Под root подготовьте внешний `group_vars/all.yml` и root-only файлы секретов.
3. В `infra/ansible` выполните:

```bash
ansible-playbook --syntax-check -i inventory/localhost.yml playbooks/deploy-prepared.yml
ansible-playbook -i inventory/localhost.yml playbooks/deploy-prepared.yml
```

4. Пройдите те же проверки панели, подписки, бота и клиентов, что и для чистого
   VPS.

Если Docker отсутствует, этот сценарий завершается ошибкой. Не устанавливайте
Docker поверх чужой установки автоматически — вернитесь к владельцу сервера или
используйте чистый VPS.
