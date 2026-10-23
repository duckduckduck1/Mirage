# Looking after my VPN

[README](../README.md) · [Installation](setup.md) · [Recovery](recovery.md)

These are my intended maintenance steps for the new setup. I still need to test
them on an isolated VPS. My [current server](migration.md) uses a different
configuration, so I cannot apply the fresh-install settings or replace its image
without preparing that migration first.

## Giving someone access

I'll create one Marzban user per person, enable Trojan and assign the
`TROJAN TCP TLS` inbound. I'll set the quota and expiry deliberately, then send
the subscription link privately. If a link leaks, I'll revoke or replace that
person's access through Marzban and check that the old credentials stop working.

For the proposed setup, the subscription uses HTTPS on 8443 and contains one
Trojan profile on 443. I need to check both subscription refresh and actual client
traffic before sharing it. Adding profiles does not establish automatic failover.

## Where my configuration lives

| Location | What I need it for |
| --- | --- |
| `/opt/marzban/docker-compose.yml` | Official deployment and selected image |
| `/opt/marzban/.env` | Marzban settings |
| `/var/lib/marzban/db.sqlite3` | Complete user and subscription state |
| `/var/lib/marzban/xray_config.json` | Inbound and routing settings |
| `/var/lib/marzban/certs/` | Certificate and private key used by both listeners |
| `/root/.acme.sh/` and root's crontab | ACME account, renewal settings and schedule |

These are the paths selected in my [installation notes](setup.md), not a reason
to assume an older installation uses them. I'll keep real settings, links and
recovery material outside Git, with restricted access.

## When something stops working

On the intended VPS, my first checks are:

```bash
sudo marzban status
sudo marzban logs
sudo journalctl -u docker --since '1 hour ago'
df -h
free -h
```

I'll note the time, affected users, network and client version before changing
settings. Logs may include private links, so I'll redact them before sharing.

| What I observe | What I'll check next |
| --- | --- |
| Everyone disconnects together | Container/core restart, renewal time, host reboot, memory and disk |
| Subscription fails but an imported profile connects | Certificate and HTTPS listener on 8443 |
| Subscription refreshes but traffic fails | User quota/expiry, inbound state, port 443 and imported address/SNI |
| Only one client fails | Imported settings, client/core version, VPN/TUN mode and routing |
| Only one Wi-Fi network fails | Same device/profile on mobile data, then client/server logs from the same attempt |

A successful TCP connection is not proof that TLS or the VPN tunnel works. Before
blaming filtering, I need evidence of which side received and answered the
request. A DNS change does not change the destination of an IP-based profile.

## Certificates

For this recipe, acme.sh renews over TCP 80, installs into
`/var/lib/marzban/certs/` and runs `/usr/local/bin/marzban restart --no-logs`.
That restart interrupts connections. I'll compare unexpected disconnect times
with renewal logs before assuming a transport problem.

After renewal, I need to check the certificate actually presented on **both**
443 and 8443, including its hostname and expiry. I'll also refresh a subscription
and test traffic. New files on disk are insufficient evidence of a successful
reload. I'll test the renewal/reload procedure in a maintenance window before
depending on it; I have not done that for this setup yet.

The scheduled installation/reload behavior comes from
[acme.sh](https://github.com/acmesh-official/acme.sh).

## Backups

My recovery copy needs to leave the VPS and be encrypted, with the decryption
key in a separate place. The [recovery notes](recovery.md) describe its contents
and a manual offline copy. I'll take one before updates and after important
configuration or user changes, and choose a recurring backup schedule once the
new setup has been tested. Until that exists, I cannot assume new users are
covered by a scheduled backup.

Marzban also has an optional
[native backup service](https://gozargah.github.io/marzban/en/docs/marzban-script).
If I enable it, I'll use `sudo marzban backup-service` to configure delivery and
`sudo marzban backup` for a manual run. Both can send data to the configured
channel. I'll verify what the delivered archive includes; it may omit my ACME
state. Delivery alone does not establish that I can restore it.

## Updates

I'll update deliberately rather than follow a moving image automatically:

1. Save a fresh recovery copy and record the current image tag/digest and Xray
   version. Keep the previous image available.
2. Read the [upstream release notes](https://github.com/Gozargah/Marzban/releases)
   and try the candidate with a restored copy in isolation, without production
   bot polling, renewal jobs or DNS changes.
3. On the intended host, change only the Marzban image in the official
   `/opt/marzban/docker-compose.yml` to the chosen release. Then run:

   ```bash
   sudo docker compose -f /opt/marzban/docker-compose.yml -p marzban pull marzban
   sudo marzban restart --no-logs
   ```

4. Check login, existing subscription links, client traffic and certificates.
   Record the actual versions and result in my private notes.

If I need to roll back, I'll restore the previous image and matching configuration.
If the new release changed the database, I'll also restore the pre-update data;
reverting only the image cannot undo a database migration. I won't independently
replace the bundled Xray unless a specific compatibility problem requires it.
