# Setup

[Back to README](../README.md)

This guide describes a **new, isolated upstream Marzban installation**. It has
not been exercised as a separate clean-install acceptance test. For the existing
Mirage VPS, read [Migration and troubleshooting](migration.md) instead.

## 1. Prepare a fresh host

Use a Linux VPS supported by the current
[official installation guide](https://gozargah.github.io/marzban/en/docs/installation).
You need administrative SSH access and `curl`. Keep the initial dashboard port
8000 closed to public ingress while preparing the service. Review the provider's
firewall and any existing Docker installation before running the installer.

The official quick installer can install Docker and creates its own Compose
deployment. There is no Mirage bootstrap step and no reason to clone this
repository onto the VPS.

Choose an official release after reviewing its release notes and the
[REALITY limitation](migration.md#reality-subscription-limitation). The command
below follows upstream's quick-start and may select a moving `latest` image.
For an explicit release, use the installer's documented `--version` option from
the [script guide](https://gozargah.github.io/marzban/en/docs/marzban-script).
An image version does not pin the downloaded installer or its templates.

## 2. Install upstream Marzban

Run **on the fresh VPS**, after reviewing the upstream script:

```bash
sudo bash -c "$(curl -sL https://github.com/Gozargah/Marzban-scripts/raw/master/marzban.sh)" @ install
```

The installer eventually follows container logs. Stop following with Ctrl+C;
the detached service continues running. Do not accept an offer to overwrite an
existing installation as part of this fresh-install procedure.

| Location | Contents |
| --- | --- |
| `/opt/marzban/docker-compose.yml` | Installer-managed deployment |
| `/opt/marzban/.env` | Application configuration and any configured credentials |
| `/var/lib/marzban` | Persistent application data |

Confirm the actual SQLite and Xray configuration paths in `.env`; do not infer
them from the current working directory. Inspect configuration privately, and
keep it out of Git and CI logs.

## 3. Open the dashboard through SSH

On the fresh VPS, run `sudo marzban edit-env`. Using the
[documented settings](https://gozargah.github.io/marzban/en/docs/configuration),
set:

```dotenv
UVICORN_HOST = "127.0.0.1"
UVICORN_PORT = 8000
DEBUG = false
DOCS = false
```

An active `UVICORN_UDS` overrides host/port settings; leave it unset for this
new-install tunnel example. Restrict `.env` to its intended owner and apply:

```bash
sudo chmod 600 /opt/marzban/.env
sudo marzban restart
sudo marzban cli admin create --sudo
```

On **your workstation**, replace the uppercase SSH placeholders and keep this
session open:

```bash
ssh -N -L 8000:127.0.0.1:8000 ADMIN_USER@SERVER_HOST
```

Open `http://127.0.0.1:8000/dashboard/` locally and sign in. If local port 8000 is
busy, change the first port in `-L` and the browser URL together.

## 4. Configure the service you need

Use upstream documentation for
[Core Settings](https://gozargah.github.io/marzban/en/docs/core-settings),
[inbounds](https://gozargah.github.io/marzban/en/docs/xray-inbounds) and
[Host Settings](https://gozargah.github.io/marzban/en/docs/host-settings).
Choose a transport supported by the actual client, configure its parameters and
open only the corresponding service ports. Do not reuse this guide as a fixed
set of four transport profiles or as proof of reachability through an ISP.

The SSH tunnel is for administration. Users on other devices need a reachable
HTTPS subscription endpoint. Follow upstream's
[TLS guide](https://gozargah.github.io/marzban/en/examples/marzban-ssl) and
[subscription guide](https://gozargah.github.io/marzban/en/docs/subscription):
obtain a certificate for your own domain, arrange renewal, configure the actual
certificate/key paths and set `XRAY_SUBSCRIPTION_URL_PREFIX` to the public HTTPS
address, including its port when needed. Transition the listener from loopback
only when TLS is configured and its intended exposure is understood.

Marzban supports `UVICORN_SSL_CERTFILE` and `UVICORN_SSL_KEYFILE` directly. This
repository does not require Caddy, DuckDNS, a particular ACME client or port 2096.
After any renewal, verify the certificate served over the network, not only the
file on disk.

Create users through the dashboard or
[official CLI](https://gozargah.github.io/marzban/en/docs/marzban-cli). The
[Telegram bot](https://gozargah.github.io/marzban/en/docs/telegram-bot) is optional.
Configure [backups](operations.md#backups) before issuing access you depend on.

## Acceptance before everyday use

Record the resolved Marzban image tag/digest, actual Xray version, OS and client
versions outside public infrastructure records. Verify dashboard login, a user
subscription over HTTPS, its returned connection parameters, real client traffic
and recovery of the saved state on an isolated host. For REALITY, include the
first subscription response after a cold application start.

A successful installer exit or an open TCP port is only one part of acceptance.
See [Operations](operations.md) and [Recovery](recovery.md).
