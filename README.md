# Mirage

My notes for running a VPN for myself and a few friends with
[Marzban](https://github.com/Gozargah/Marzban).

## My notes

1. [Installation](docs/setup.md): a fresh Ubuntu VPS, official Marzban, one Trojan
   TCP/TLS inbound, a domain and HTTPS subscriptions.
2. [Maintenance](docs/operations.md): give someone access, check failures, renew
   certificates, back up and update.
3. [Recovery](docs/recovery.md): restore the server without recreating users or
   replacing their subscription links.

**Status: proposed setup, not yet tested end to end.** Commands and settings were
checked against upstream sources on 2026-10-23. Installation, certificate renewal,
client traffic and restoration still need a separate test on an isolated VPS.
There is no claim that this transport works through every Russian ISP or campus
network.

My existing server still runs the previous configuration. I need to prepare its
migration separately rather than run a fresh installation over it. Its dependencies
and migration requirements are in [existing-server notes](docs/migration.md).

I don't need to clone this repository onto the VPS: Marzban provides its own
installer and Docker Compose deployment. My actual settings, credentials and
encrypted backups belong outside this public repository.

## Reference

[Previous deployment source](https://github.com/duckduckduck1/Mirage/tree/legacy-ansible-2026-10-23)
· [Historical observations](audit/acceptance-ledger.md)
· [Changelog](CHANGELOG.md) · [MIT license](LICENSE)

For edits, I can run `python3 scripts/check.py` with Python 3.10+ and Git.
It checks local Markdown links and common accidental secret additions, not the
server or VPN connectivity.
