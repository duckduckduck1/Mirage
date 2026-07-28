# Requirements

The supported flow needs a new 64-bit Ubuntu 22.04 LTS VPS, root SSH access,
and the TCP ports listed in the [reference](/en/reference/ports).

Prepare outside Git:

- an administrator public SSH key;
- separate root-only files for DNS, ACME, and Telegram data;
- a permanent DNS name controlled by the owner;
- a Marzban administrator account created only by the native CLI;
- external storage for backup archives.

For clean-VPS acceptance, use separate test DNS and Telegram data. Never point
the production name at the test host or run a second server with the production
bot token.
