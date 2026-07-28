# Restore from an archive

Mirage uses only the native Marzban SQLite archive. The official procedure
restores `/opt/marzban` and `/var/lib/marzban`, then requires an explicit
`marzban restart`.

1. Deploy the base infrastructure with one installation flow first.
2. Keep the received archive outside the Git checkout, make it owned by `root`,
   and restrict it to mode `0600`.
3. Run the restore flow with an absolute path:

```bash
ansible-playbook -i inventory/localhost.yml playbooks/restore.yml \
  -e 'marzban_restore_archive=/root/restore/marzban-backup.tar.gz'
```

The playbook accepts only a regular root-owned tar archive whose paths are under
`/opt/marzban` and `/var/lib/marzban`; other paths are rejected before extraction.
It reapplies the infrastructure roles, restarts Marzban, and waits for the panel
Unix socket.

Check the dashboard, user count, HTTPS subscription, bot, and external client
traffic. An archive is not a backup until restoration has been tested.
