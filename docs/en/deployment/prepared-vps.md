# Prepared VPS

Use this flow when Docker Compose is already installed or the VPS is not clean.
The playbook does not replace Docker and verifies `docker compose version`
before any change.

1. Confirm that Docker and its data belong to Mirage's scope or were accepted
   separately by the server owner.
2. As root, prepare external `group_vars/all.yml` and root-only secret files.
3. In `infra/ansible`, run:

```bash
ansible-playbook --syntax-check -i inventory/localhost.yml playbooks/deploy-prepared.yml
ansible-playbook -i inventory/localhost.yml playbooks/deploy-prepared.yml
```

4. Perform the same dashboard, subscription, bot, and client checks as for a
clean VPS.

If Docker is absent, this flow fails. Do not automatically install Docker over
an existing shared setup; return to the server owner or use a clean VPS.
