# Recovering my server

[README](../README.md) · [Installation](setup.md) · [Maintenance](operations.md)

I want to be able to lose the VPS and restore access without asking everyone to
import new subscriptions. This is my proposed procedure for the new setup; I
have not tested a restoration of it yet. My [existing server](migration.md)
also needs its patched image and other legacy dependencies.

## What I'll keep outside the VPS

- `/opt/marzban/`: deployment file and `.env`.
- `/var/lib/marzban/`: complete SQLite state, Xray configuration and installed
  certificates/keys.
- `/root/.acme.sh/` and the relevant root crontab entry: account, renewal and
  install/reload settings. This contains private keys too.
- A private note with the hostname, DNS access, selected image tag/digest, bundled
  Xray version and client versions I actually tested. I'll retain the image itself
  if I cannot rely on downloading it later.

I'll encrypt this bundle outside the VPS and keep its decryption key separately.
Nothing in that list belongs in this public checkout. The official
[backup guide](https://gozargah.github.io/marzban/en/examples/backup) covers the
application directories; my ACME state is an additional dependency of this recipe.

## A simple consistent copy

For an occasional manual backup, I'll accept a short outage and stop Marzban
before copying SQLite. I'll pause the ACME cron entry and wait for any running
renewal to finish so it cannot restart Marzban during the copy. On the intended
**VPS**, after checking there is enough disk space:

```bash
sudo -i
umask 077
recovery_dir=$(mktemp -d /root/marzban-recovery.XXXXXXXX)
crontab -l > "$recovery_dir/root-crontab.txt"
docker compose -f /opt/marzban/docker-compose.yml -p marzban stop marzban
tar -C / -czf "$recovery_dir/server.tar.gz" opt/marzban var/lib/marzban root/.acme.sh
marzban restart --no-logs
exit
```

These are individual steps, not a script to run unattended. I'll proceed with
`tar` only after the stop succeeds. If `tar` fails, I still need to restart the
service and resolve the backup failure. I'll restore the paused ACME schedule
after the copy and service restart. I'll record the
generated directory path privately, transfer both files over SSH to my trusted
workstation, encrypt them there using my chosen backup tool and check that I can
decrypt/read the copy. Then I'll remove the temporary plaintext copies from the
VPS and workstation. I have not chosen or tested an automated encrypted backup
destination for this recipe yet.

This is my own offline directory archive, not Marzban's native backup format.
For a native archive, I'll inspect its contents first: the
[producer script](https://github.com/Gozargah/Marzban-scripts/blob/master/marzban.sh)
may package the database/configuration separately and exclude a custom Xray core.
I cannot restore different formats by assuming the same archive layout.

## My local encrypted files

For my existing deployment, I keep private recovery material outside the checkout
in `~/.local/share/mirage/`. Its private `README.md` records the archive/key paths
and how to decrypt to a private staging directory. The former loose `access`,
`bot_telegram_key` and `duckdns_token` files are in an encrypted archive there;
I verified their decrypted bytes before removing the plaintext originals.

The separate key files are under `~/.config/mirage/`, with access restricted to my
account. This is a local encrypted archive, not a password manager. I still need
an independent copy of the encrypted files and to put the keys in my password
manager. Keeping everything on one computer does not cover losing that computer.
My documentation CI does not need these credentials, so I have not uploaded them
to GitHub Actions secrets.

## Restore in isolation first

1. On an isolated VPS, install the same official Marzban release. Stop it before
   replacing its data. I'll preserve any destination state I might still need.
2. Decrypt and inspect the archive privately. For the manual copy above, the paths
   start with `opt/marzban`, `var/lib/marzban` and `root/.acme.sh`. I'll extract to
   a private staging directory and check paths/link targets before placing the
   files back at those locations. I won't extract an unchecked archive into `/`.
3. Restore the complete database and matching configuration, ownership and
   restrictive permissions. Keep restored cron jobs disabled, along with any bot
   polling or delivery. The clone must not renew production certificates, update
   live DNS or expose copied user access.
4. Keep the clone's firewall private. Start with `sudo marzban restart --no-logs`.
   Copying files does not reload the application.
5. Check SQLite integrity, administrator login, users, quotas, inbound assignments,
   existing subscription tokens and client traffic. On my test workstation, I can
   temporarily resolve the original hostname to the clone while keeping public
   DNS unchanged. I'll record the versions, result and recovery time privately.

For a real replacement, I'll switch DNS only after the restoration checks,
including the certificate served on both ports. I'll review and deliberately
reenable the required renewal schedule; I won't overwrite an unrelated root
crontab wholesale. For a planned migration, I'll freeze user changes and take a
final consistent copy before switching.

## Why a list of users isn't enough

I need the complete database, including proxy credentials, user state, assignments,
Host Settings and the subscription signing secret. Recreating matching usernames
does not preserve all of that and can invalidate old links. The public hostname,
port, subscription path and signing state also need to survive. I'll verify an
already issued subscription, not just create a new user and call the restore done.
