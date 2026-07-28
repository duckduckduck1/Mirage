# Maintenance

Before changing Marzban, Xray-core, iOS, or a client application, create a
verified backup and schedule a new client matrix. Xray-core is pinned; updating
it is allowed only after the full supported-transport check.

Regularly check:

- dashboard and HTTPS subscription availability;
- Telegram bot operation;
- backup delivery;
- Marzban, Caddy, and Docker startup after a VPS reboot.

On a shared VPS, never use `docker system prune`, broad deletion, or operations
on containers, volumes, and networks that do not belong to Mirage.
