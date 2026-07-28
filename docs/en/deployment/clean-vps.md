# Clean VPS

This flow is only for a new Ubuntu 22.04 host without Docker, containers, or
Docker data. The `docker_engine` role installs Docker Engine and the Compose
plugin from Docker's official APT repository. It stops without changing anything
if Docker or its data already exists.

1. As root, install Ansible and Git, then obtain the `dev` branch or an accepted
   Mirage release.
2. In `infra/ansible`, create ignored `group_vars/all.yml` from
   `group_vars/all.example.yml` and keep secrets in root-only files outside the
   checkout.
3. Set approved values and enable the required Marzban, Xray, certificate,
   inbound, Caddy, and Telegram roles. Do not invent settings; check the
   [official Marzban documentation](https://gozargah.github.io/marzban/en/docs/introduction).
4. Run the syntax check, then the flow:

```bash
ansible-playbook --syntax-check -i inventory/localhost.yml playbooks/deploy-clean.yml
ansible-playbook -i inventory/localhost.yml playbooks/deploy-clean.yml
```

5. Create the Marzban administrator with its native CLI and test the dashboard,
HTTPS subscription, bot, and supported client profiles.

Do not run this playbook on a shared or configured VPS; use the
[prepared-VPS flow](/en/deployment/prepared-vps).
