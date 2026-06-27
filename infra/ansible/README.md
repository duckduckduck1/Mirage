# Mirage Ansible bootstrap

Этот каталог содержит первый Ansible-этап для свежего VPS. Он запускается прямо
на сервере и применяет настройки к `localhost`.

## Что делает playbook

- создаёт бэкап административных файлов в `/root/mirage-backups/`;
- создаёт пользователя `mirage`;
- добавляет публичный SSH-ключ;
- выдаёт пользователю `mirage` sudo-доступ для автоматизации;
- ставит базовые пакеты, `ufw` и `fail2ban`;
- открывает порты `22/tcp` и `443/tcp`;
- держит неиспользуемые резервные порты, включая `8388/tcp`, закрытыми по умолчанию;
- включает SSH-hardening только при явном `enable_ssh_hardening=true`;
- кладёт SSH-hardening в `01-mirage-hardening.conf`, чтобы настройки применились
  раньше cloud-init.

## Быстрый запуск

Сначала положи публичный ключ на VPS:

```bash
mkdir -p /root/.ssh
nano /root/.ssh/mirage_ed25519.pub
chmod 600 /root/.ssh/mirage_ed25519.pub
```

Установи Ansible и Git, если они ещё не установлены:

```bash
apt update
apt install -y ansible git
```

Затем запусти bootstrap:

```bash
cd /root/mirage/infra/ansible
ansible-playbook --syntax-check site.yml
ansible-playbook site.yml
```

Проверь вход с локальной машины:

```bash
ssh -i ~/.ssh/mirage_ed25519 mirage@SERVER_IP
```

Только после успешной проверки включай hardening:

```bash
ansible-playbook site.yml -e enable_ssh_hardening=true --tags hardening
```

После повторной проверки нового SSH-входа отмени rollback-таймер:

```bash
sudo systemctl stop mirage-ssh-rollback.timer mirage-ssh-rollback.service
```

Полный порядок действий описан в
[runbook для Ansible-bootstrap](../../docs/runbooks/bootstrap-vps-ansible.md).
