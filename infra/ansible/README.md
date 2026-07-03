# Ansible bootstrap

Этот playbook готовит свежий VPS к установке Mirage.

Он создаёт пользователя `mirage`, добавляет SSH-ключ, выдаёт sudo-доступ,
включает `ufw`, ставит `fail2ban` и может включить SSH-hardening после проверки
нового входа.

## Запуск

На свежем VPS под `root`:

```bash
apt update
apt install -y ansible git
git clone --branch dev https://github.com/duckduckduck1/Mirage.git /root/mirage
cd /root/mirage/infra/ansible
ansible-playbook --syntax-check site.yml
ansible-playbook site.yml
```

После проверки входа под `mirage`:

```bash
ansible-playbook site.yml -e enable_ssh_hardening=true --tags hardening
```

Полный порядок установки описан в [руководстве Mirage](../../docs/guide.md).
