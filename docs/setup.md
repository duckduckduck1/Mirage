# Installing my VPN on a fresh VPS

[README](../README.md) · [Maintenance](operations.md) · [Recovery](recovery.md)

**Proposed recipe, not an installation result.** Source review: 2026-10-23.
This is the procedure I plan to try on a separate fresh VPS. My
[existing server](migration.md) has different dependencies and subscription
identity to preserve; I have not changed it as part of these notes.

## What I chose

| Item | Choice |
| --- | --- |
| Host | Fresh Ubuntu 24.04 LTS VPS with administrative SSH access |
| Application | Official Marzban v0.8.4 image, bundled Xray, SQLite |
| Client connection | One Trojan TCP/TLS inbound on TCP 443 |
| Dashboard and subscriptions | Marzban's own HTTPS listener on TCP 8443 |
| Certificate | Let's Encrypt through acme.sh, standalone HTTP validation |
| Example hostname | `vpn.example.com`, replaced everywhere with my domain |

I chose one transport with ordinary TLS certificates to keep the initial setup
small. I still need to test whether it works on the networks my friends and I use.
The [official v0.8.4 release](https://github.com/Gozargah/Marzban/releases/tag/v0.8.4)
is my candidate for this recipe; I have not tested it here. I will review the
release again before installing. I have not included REALITY in this setup; its
`sid` compatibility issue still matters for my [existing deployment](migration.md#reality-subscription-limitation).

## 1. Prepare the domain and ports

I need a DNS-only A record pointing my hostname to the new VPS. I will leave out
AAAA unless I also configure and test IPv6. A CDN proxy is not part of this direct
TCP setup.

My provider and host firewalls need these incoming TCP connections:

| TCP port | Access | Purpose |
| --- | --- | --- |
| My SSH port | My administration network | Administration |
| 80 | Internet | Certificate issuance and future HTTP renewals |
| 443 | Internet | Trojan client traffic |
| 8443 | Internet, after TLS is configured | Dashboard and subscriptions |

I will keep 8000 and other unneeded inbound ports closed. Port 80 must be free for
acme.sh to bind during issuance and renewal. Outbound package downloads, DNS,
ACME requests and proxied client traffic must be allowed. This assumes a fresh
host without another web server or existing Marzban installation.

## 2. Install Marzban and open the initial dashboard

On the **new VPS**, I first need `curl`:

```bash
sudo apt update
sudo apt install -y curl
```

After reviewing the [official installer](https://github.com/Gozargah/Marzban-scripts/blob/master/marzban.sh),
I will run its install command with an explicit image version:

```bash
sudo bash -c "$(curl -fsSL https://github.com/Gozargah/Marzban-scripts/raw/master/marzban.sh)" @ install --version v0.8.4
```

The upstream script installs Docker if needed and supplies its own Compose file.
It downloads a moving installer and templates; the image version does not pin
those files. Ctrl+C stops following the installation logs without stopping the
detached service. If it offers to overwrite an installation, I will stop here.

In `sudo marzban edit-env`, I will replace these entries rather than append
duplicates, and leave `UVICORN_UDS` unset:

```dotenv
UVICORN_HOST = "127.0.0.1"
UVICORN_PORT = 8000
DEBUG = false
DOCS = false
XRAY_JSON = "/var/lib/marzban/xray_config.json"
SQLALCHEMY_DATABASE_URL = "sqlite:////var/lib/marzban/db.sqlite3"
```

Then I will apply the settings and create my administrator interactively:

```bash
sudo chmod 600 /opt/marzban/.env
sudo chmod 700 /var/lib/marzban
sudo marzban restart --no-logs
sudo marzban cli admin create --sudo
```

On **my workstation**, I will replace the SSH placeholders and keep this tunnel
open:

```bash
ssh -N -L 8000:127.0.0.1:8000 ADMIN_USER@SERVER_HOST
```

I should then be able to sign in at `http://127.0.0.1:8000/dashboard/`. I will
keep the administrator password in my password manager.

## 3. Obtain and install the certificate

On the **new VPS**, I will use a root shell for certificate setup. After reviewing
the [acme.sh installer and renewal behavior](https://github.com/acmesh-official/acme.sh),
I will replace the example email and hostname and run:

```bash
sudo -i
apt install -y socat cron
systemctl enable --now cron
curl -fsSL https://get.acme.sh | sh -s email=admin@example.com
/root/.acme.sh/acme.sh --issue --server letsencrypt --standalone -d vpn.example.com --keylength ec-256
install -d -m 700 /var/lib/marzban/certs
umask 077
/root/.acme.sh/acme.sh --install-cert --ecc -d vpn.example.com \
  --key-file /var/lib/marzban/certs/key.pem \
  --fullchain-file /var/lib/marzban/certs/fullchain.pem \
  --reloadcmd '/usr/local/bin/marzban restart --no-logs'
exit
```

The install command copies certificates into the directory mounted by upstream
Compose and saves the reload command for renewal. It also runs that command now.
The root acme.sh installation schedules renewal through root's crontab. I'll
inspect it privately to confirm the entry exists before relying on it.

**Renewal restarts Marzban and interrupts active connections.** This recipe
accepts that interruption to reload both the application and Xray certificates;
I am not promising uninterrupted renewal.
`--no-logs` lets the renewal command finish instead of following logs forever.
Actual scheduled renewal and the certificates served afterwards remain untested.

## 4. Enable HTTPS for the dashboard and subscriptions

In `sudo marzban edit-env`, I will change the listener settings and add my
certificate paths and public subscription address:

```dotenv
UVICORN_HOST = "0.0.0.0"
UVICORN_PORT = 8443
UVICORN_SSL_CERTFILE = "/var/lib/marzban/certs/fullchain.pem"
UVICORN_SSL_KEYFILE = "/var/lib/marzban/certs/key.pem"
XRAY_SUBSCRIPTION_URL_PREFIX = "https://vpn.example.com:8443"
```

I need to replace the hostname, keep `UVICORN_UDS` unset and retain the other
settings from step 2. After `sudo marzban restart --no-logs`, I will allow public
TCP 8443 and open `https://vpn.example.com:8443/dashboard/`. Once the browser trusts
the certificate and login works, I can close the SSH tunnel. I will resolve any
certificate errors rather than bypass them.

This choice publicly exposes the HTTPS dashboard and API alongside subscriptions,
so I need a strong unique administrator password. Keeping the dashboard private
would need a different exposure design. Upstream documents these
[native TLS settings](https://gozargah.github.io/marzban/en/examples/marzban-ssl).

## 5. Add the one client inbound

In the dashboard's **Core Settings**, I will use the JSON below, replacing
`vpn.example.com`. It combines the
[upstream base configuration](https://github.com/Gozargah/Marzban/blob/v0.8.4/xray_config.json)
with its [Trojan TCP TLS inbound](https://gozargah.github.io/marzban/en/docs/xray-inbounds#tls).
This replacement is for my fresh installation only; it would discard other inbounds.

```json
{
  "log": {"loglevel": "warning"},
  "routing": {
    "rules": [
      {"type": "field", "ip": ["geoip:private"], "outboundTag": "BLOCK"}
    ]
  },
  "inbounds": [
    {
      "tag": "TROJAN TCP TLS",
      "listen": "0.0.0.0",
      "port": 443,
      "protocol": "trojan",
      "settings": {"clients": []},
      "streamSettings": {
        "network": "tcp",
        "security": "tls",
        "tlsSettings": {
          "serverName": "vpn.example.com",
          "minVersion": "1.2",
          "certificates": [
            {
              "certificateFile": "/var/lib/marzban/certs/fullchain.pem",
              "keyFile": "/var/lib/marzban/certs/key.pem"
            }
          ]
        }
      }
    }
  ],
  "outbounds": [
    {"protocol": "freedom", "tag": "DIRECT"},
    {"protocol": "blackhole", "tag": "BLOCK"}
  ]
}
```

After saving/applying in the panel, I will check `sudo marzban status` and
`sudo marzban logs` for startup or certificate errors. Marzban populates `clients`
from its database, so I will leave that array empty in the base JSON.

In **Host Settings**, I will set the host for `TROJAN TCP TLS`:

| Field | Value |
| --- | --- |
| Remark | `Personal VPN` |
| Address | My hostname, replacing `vpn.example.com` |
| Port | `443` |
| SNI | The same hostname |
| Security layer | TLS |

I will leave unrelated transport overrides at their defaults. These fields determine
the generated client profiles; see upstream
[Host Settings](https://gozargah.github.io/marzban/en/docs/host-settings).

## 6. My first user and client test

1. I will create one test user, enable Trojan and assign only `TROJAN TCP TLS`,
   with an explicit quota and expiry.
2. I will copy that user's HTTPS subscription link from the dashboard and check
   that it uses my hostname and port 8443. The whole URL is a credential.
3. I will add it as a remote subscription in Hiddify or Karing, refresh and select
   the Trojan profile. Those clients were used on my older setup; I have not
   tested their current versions with this recipe.
4. I will check the imported address, port 443, TLS and matching SNI, leaving
   certificate verification enabled. For traffic from other applications, I need
   the client's system VPN/TUN mode and a test outside the client itself.
5. I will repeat on the networks I need, including mobile data and the relevant
   Wi-Fi, and record the results. An open port or successful import is insufficient.

Before giving friends access, I need an [external recovery copy](recovery.md),
an isolated restoration test and a renewal/reload test in a maintenance window.
I will record the actual image digest, bundled Xray and client versions and the
results privately. These checks are still pending for this recipe.
