# Migration from Marzban

[README](../README.md) · [Setup](setup.md) · [Operations](operations.md) · [Recovery](recovery.md)

**Status: production switched to official 3x-ui on 2026-10-25.**
Four users and four transports passed server-side traffic/subscription checks.
Legacy data is retained for rollback; observation and client acceptance remain separate.
Historical checks below apply to Marzban. They are not acceptance of the new setup.

## Retained legacy deployment

Observed after maintenance on 2026-10-24:

| Component | Configuration |
| --- | --- |
| OS | Ubuntu 22.04 |
| Panel | Marzban v0.8.4, A-13 derivative, SQLite |
| Core | Xray v26.7.28 through `XRAY_EXECUTABLE_PATH` |
| Transports | TCP REALITY 443; gRPC REALITY 8443; XHTTP REALITY 2053; Trojan TLS 9443 |
| Panel/subscriptions | Caddy HTTPS 2096 to Marzban's Unix socket |
| Certificates/DNS | Host acme.sh DNS-01 and DuckDNS updater |

Legacy source is preserved at
[`legacy-ansible-2026-10-23`](https://github.com/duckduckduck1/Mirage/tree/legacy-ansible-2026-10-23),
commit `bf3c47e90f7b1be7898f8be14f6658ced7d0db32`, including the Caddy forced-reload
repair. Credentials, infrastructure addresses and recovery material are private.
Removing repository automation does not remove installed services or dependencies.

### Maintenance evidence: 2026-10-23

- Forced Caddy reload corrected an old certificate still served despite renewed
  files. The existing hook still restarts Marzban on renewal and can interrupt traffic.
- Four active users passed twelve generic/Hiddify/Karing subscription requests.
  Generic output had four profiles; Hiddify/Karing had three. The installed
  sing-box generator explicitly excludes XHTTP.
- All four transports passed HTTPS with a temporary server-loopback client.
  Those checks did not establish reachability from affected external networks.
- An encrypted external recovery copy passed decryption, archive and SQLite
  integrity checks. Full restoration remains untested. Data permissions were
  restricted to directory 0700/database 0600; the obsolete 3x-ui backup timer was
  disabled. Native Marzban backup delivery was not retested.
- A separate failed Certbot lineage still has configuration references. Its role
  must be established before removal; it does not own the working acme.sh certificate.

### Maintenance evidence: 2026-10-24

A REALITY failure was reproduced with the old server and newer client, including
through SSH, without requiring ISP filtering or TUN. Xray v26.7.28 defaults reject
older REALITY clients. The approved repair upgraded the server from v24.12.31,
explicitly retained `minClientVer=1.8.0` and supplied the existing public keys.
Marzban v0.8.4 cannot parse modern x25519 output; automatic key generation remains
limited. See [upstream issue #1938](https://github.com/Gozargah/Marzban/issues/1938).

The restart preserved A-13, users, credentials, signing state, ports and URLs.
Caddy did not restart. Previous core/configuration remain available for rollback;
the earlier encrypted archive restores the pre-update state.

Verified after restart:

- Sixteen subscription responses: four users × generic, Hiddify, Karing and
  Xray JSON. Private connection parameters matched before/after. Profile counts
  were four, three, three and four respectively.
- The existing Throne subscription returned HTTP 200 with an identical body.
- Sixteen server-loopback user/transport combinations passed HTTPS traffic.
- Laptop physical-Wi-Fi tests passed all four profiles with both Xray v24.12.31
  and v26.7.28; official sing-box v1.13.16 passed TCP, gRPC and Trojan.
- XHTTP downloaded exactly 1 MiB and passed three repeated HTTPS requests.
  These fifteen external checks did not change the active GUI VPN.
- The running container used the new core. Served Trojan/subscription certificates
  matched installed files and expire on 2026-12-25; no startup traceback was observed.

Throne GUI/TUN endurance, Beeline, campus Wi-Fi and mobile allowlists remain
unconfirmed. Full replacement-panel acceptance is separate from this repair.

### A-13 and historical clients

Official Marzban v0.8.4 can omit REALITY `sid` in the first subscription after
startup. A-13 applies the one-line change from
[PR #2036](https://github.com/Gozargah/Marzban/pull/2036), described in
[issue #1986](https://github.com/Gozargah/Marzban/issues/1986). Replacing it with an
unmodified image requires cold-start and repeated-subscription checks first.

Historical acceptance on **2026-07-28** confirmed TCP REALITY, gRPC REALITY and
Trojan in Hiddify/Karing. XHTTP was not working in those client tests. V2RayTun,
V2Box, Streisand and OneXray were not confirmed. Exact client/OS builds were not
retained, and automatic-failover/multi-network acceptance was incomplete. See the
[historical ledger](../audit/acceptance-ledger.md). Do not generalize these results
to current clients or the proposed installation.

## Migration to 3x-ui

Target: official prebuilt 3x-ui, SQLite and Caddy under Compose. No application
fork, submodule or custom build. [Candidate review](../audit/3x-ui-candidate.md)
separates local artifact checks from subsequent VPS preparation.

### Preparation and isolated test

Server access requires separate authorization. Inventory current images, ports,
jobs, ownership, memory and disk. Obtain a fresh encrypted recovery set of the
repaired Marzban, A-13 image, Xray v26.7.28, SQLite/signing state, configuration,
TLS/ACME, Caddy and four external maintenance scripts. The older archive is not a
fresh recovery copy of the repaired core.

Keep existing services running during preparation. The original concurrent-test
budget was 512 MiB available memory. On this host, the owner instead approved a
sequential test with Marzban stopped, unchanged container caps and immediate
rollback below 128 MiB available memory, on OOM or unexpected failure. The
controlled test passed; the later production switch was explicitly authorized.
See the [memory and interruption procedure](setup.md#test-isolation).
Keep separate data/network, alternate ports and a new bot. Stop on pressure or
OOM. Keep production DNS, ACME hooks and the active GUI VPN unchanged during
isolated testing; change production consumers only during the approved cutover.
Several transports on one IP do not provide independent IP redundancy.

Transfer all users through native tools. Preserve UUID/password, state, expiry,
remaining quota and four assignments; do not import Marzban tables or its entire
core output. Preserve transport identity and routing requirements. Test actual
and advertised ports must agree. Never map exhausted finite quota to unlimited.

### Acceptance matrix

| Check | Required evidence |
| --- | --- |
| Artifact | Exact image digest, architecture, revision and actual core; unexplained mismatch blocks cutover |
| Users/traffic | Every user through each of four transports; real HTTPS payload |
| XHTTP | Repeated connections and file download with exact byte count |
| Subscriptions | Raw/Base64 and Xray JSON; private field comparison, first response after cold start and repeats |
| Throne | Four profiles, refresh, system proxy, TUN, sleep and Wi-Fi reconnect |
| Hiddify/Karing | Import, refresh and supported-profile traffic; XHTTP needs a separate positive test |
| Recreate | Database, settings and issued 3x-ui links survive container replacement |
| Telegram | Owner admin access, rejection of foreign admin actions, one poller |
| TLS | Both served certificates update; active transfer continues without VPN restart |
| Recovery | Downloaded encrypted parts and matching images restore users, links and traffic in isolation |
| Observation | At least 48 hours without unexplained restarts or growing memory |

Record actual client/core versions and test paths privately. Beeline, campus and
allowlist claims require observations from those networks.

### Cutover

After acceptance and explicit authorization for interruption, reserve up to
30 minutes. Freeze administrative writes, take fresh consistent copies of both
systems and reconcile final users, expiry and quota balances. Stop the test and
prepare separate production data with the original ports. Retain the old images,
database/configuration, Caddy and ACME reload-hook together.

Stop Marzban and old Caddy to free their ports, then start the new Compose project.
Immediately check TLS, both subscription formats and every user/transport. If
initial acceptance is not successful within ten minutes, roll back.

URLs and administrative API change to native 3x-ui interfaces. Marzban token/API
compatibility is not implemented. Retrieve new subscriptions through the admin
bot and distribute them privately. Retain old subscriptions in clients for
rollback. Preserved cached credentials are not subscription-URL compatibility.
The four VPN ports and validated credentials remain unchanged.

### Rollback and observation

Roll back immediately on missing users, incorrect credentials/TLS, transport
regression or unstable processes. Stop the new project, preserve diagnostics,
and restore matching Marzban/Caddy data/images and the ACME hook. Check old links
and all transports; restore the saved client subscription where needed. New
3x-ui URLs do not refresh against Marzban. Measure the target of ten minutes from
the rollback decision in rehearsal.

Freeze user/access settings for seven days and keep the old deployment stopped.
For finite quotas on rollback, subtract measured post-cutover usage from the
cutover remaining balance; do not reset the allowance. After successful observation
and recovery rehearsal, remove only confirmed obsolete Marzban/A-13 components.
Establish dependencies before changing ACME, DNS, SSH safeguards or unrelated
services. Do not broadly prune images or remove ignored project leftovers.
