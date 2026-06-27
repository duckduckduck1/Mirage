# Bootstrap VPS через Ansible

Runbook описывает первый безопасный вход на свежий VPS и перевод доступа с root
по паролю на пользователя `mirage` по SSH-ключу.

Главное правило: **не закрывай текущую root-сессию**, пока не проверишь новый вход
по ключу в отдельном терминале.

## Что подготовить локально

На локальной машине должен быть публичный ключ:

```powershell
Get-Content $HOME\.ssh\mirage_ed25519.pub
```

Публичный ключ можно копировать на сервер. Приватный ключ
`mirage_ed25519` никогда не копируй на VPS и не передавай во внешние каналы.

## Первый вход на VPS

Подключись по временному root-паролю:

```bash
ssh root@SERVER_IP
```

Если SSH ещё не доверяет серверу, проверь fingerprint в панели провайдера, если
она его показывает. Это защищает от подключения не к той машине.

## Установка Ansible и репозитория

Обнови пакеты и поставь инструменты:

```bash
apt update
apt install -y ansible git
```

Загрузи ветку `dev` на сервер:

```bash
git clone --branch dev https://github.com/duckduckduck1/Mirage.git /root/mirage
```

Если Git-доступа с VPS нет, передай каталог проекта с локальной машины через
`scp` или архив. На сервере итоговый путь должен быть `/root/mirage`.

## Передача публичного ключа

На VPS создай файл с публичным ключом:

```bash
mkdir -p /root/.ssh
nano /root/.ssh/mirage_ed25519.pub
chmod 600 /root/.ssh/mirage_ed25519.pub
```

Вставь туда содержимое `mirage_ed25519.pub`. Это не секрет, но в git его всё равно
не нужно добавлять.

## Bootstrap без SSH-hardening

Перейди в каталог Ansible:

```bash
cd /root/mirage/infra/ansible
```

Проверь синтаксис:

```bash
ansible-playbook --syntax-check site.yml
```

Запусти первый этап:

```bash
ansible-playbook site.yml
```

Этот запуск создаёт бэкап в `/root/mirage-backups/`, пользователя `mirage`,
sudo-доступ, базовые пакеты, `ufw` и `fail2ban`. По умолчанию публично открыты
только `22/tcp` и `443/tcp`; неиспользуемые резервные порты закрыты. Парольный
вход SSH пока не отключается.

## Проверка нового доступа

Открой новый терминал на локальной машине и проверь вход:

```bash
ssh -i ~/.ssh/mirage_ed25519 mirage@SERVER_IP
```

На сервере проверь sudo:

```bash
sudo -n true
```

Проверь firewall:

```bash
sudo ufw status
```

Ожидаемый минимум после production-bootstrap:

```text
22/tcp ALLOW
443/tcp ALLOW
```

Если вход по ключу не работает, не продолжай hardening. Сохрани root-сессию и
смотри `/root/mirage-backups/`, права на `/home/mirage/.ssh` и содержимое
`authorized_keys`.

## SSH-hardening с rollback

Когда вход `mirage` по ключу точно работает, включи hardening:

```bash
cd /root/mirage/infra/ansible
ansible-playbook site.yml -e enable_ssh_hardening=true --tags hardening
```

Playbook создаёт drop-in файл
`/etc/ssh/sshd_config.d/01-mirage-hardening.conf`, проверяет `sshd -t`, делает
`reload` SSH и запускает rollback-таймер на 5 минут.

Файл начинается с `01-`, чтобы SSH прочитал его раньше cloud-init drop-in
`50-cloud-init.conf`. Это важно на Ubuntu-образах, где cloud-init может включать
`PasswordAuthentication yes`.

Сразу открой новую SSH-сессию:

```bash
ssh -i ~/.ssh/mirage_ed25519 mirage@SERVER_IP
```

Если вход работает, отмени rollback-таймер:

```bash
sudo systemctl stop mirage-ssh-rollback.timer mirage-ssh-rollback.service
```

Если вход не работает и ты ничего не отменяешь, rollback-скрипт уберёт hardening
drop-in и перезагрузит SSH-конфигурацию.

## Что проверить после hardening

Проверь, что ключевой вход работает:

```bash
ssh -i ~/.ssh/mirage_ed25519 mirage@SERVER_IP
```

Проверь эффективные настройки SSH:

```bash
sudo /usr/sbin/sshd -T | grep -E 'passwordauthentication|kbdinteractiveauthentication|permitrootlogin|pubkeyauthentication'
```

Ожидаемые значения:

```text
pubkeyauthentication yes
passwordauthentication no
kbdinteractiveauthentication no
permitrootlogin without-password
```

Фраза `without-password` — это системное отображение режима
`prohibit-password`: root больше не входит по паролю. В некоторых версиях OpenSSH
вывод может быть `prohibit-password`; смысл тот же.
