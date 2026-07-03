# Mirage Ansible bootstrap

Этот каталог содержит первый Ansible-этап для свежего VPS. Playbook запускается
прямо на сервере и применяет настройки к `localhost`.

## Что делает playbook

- создаёт бэкап административных файлов в `/root/mirage-backups/`;
- создаёт пользователя `mirage`;
- добавляет публичный SSH-ключ;
- выдаёт `mirage` sudo-доступ для автоматизации;
- ставит базовые пакеты, `ufw` и `fail2ban`;
- открывает `22/tcp` и `443/tcp`;
- включает SSH-hardening только при `enable_ssh_hardening=true`;
- пишет SSH-hardening в `01-mirage-hardening.conf`.

## Быстрый запуск

```bash
apt update
apt install -y ansible git
git clone --branch dev https://github.com/duckduckduck1/Mirage.git /root/mirage
cd /root/mirage/infra/ansible
ansible-playbook --syntax-check site.yml
ansible-playbook site.yml
```

После проверки нового SSH-входа:

```bash
ansible-playbook site.yml -e enable_ssh_hardening=true --tags hardening
```

Полный порядок:
[Bootstrap VPS через Ansible](../../docs/runbooks/bootstrap-vps-ansible.md).
