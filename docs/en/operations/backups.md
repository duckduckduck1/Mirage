# Backups

Marzban creates and delivers backups with its native `backup-service`. Configure
the schedule, an immediate backup, and delivery only according to the
[official Marzban guide](https://gozargah.github.io/marzban/en/examples/backup).

Minimum procedure:

- keep delivered archives outside the VPS and Git;
- periodically verify archive delivery;
- test restoration on a temporary server after every procedure change;
- always run `marzban restart` after extraction.

Do not publish archives, SQLite files, `.env`, or their contents in issues,
chats, or CI systems.
