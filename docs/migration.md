# My existing server

[Back to README](../README.md)

## Why these notes are separate

My main guide now describes a proposed fresh installation. My running VPS still
uses the earlier setup, so I need these notes until I migrate it. Its source is at
[`legacy-ansible-2026-10-23`](https://github.com/duckduckduck1/Mirage/tree/legacy-ansible-2026-10-23),
which points to commit `bf3c47e90f7b1be7898f8be14f6658ced7d0db32` and includes
the Caddy forced-reload repair.

The last observed deployment on 2026-10-23 had:

| Component | Observed configuration |
| --- | --- |
| OS | Ubuntu 22.04 |
| Marzban | v0.8.4 with the temporary A-13 image patch, SQLite |
| Xray | v24.12.31 through `XRAY_EXECUTABLE_PATH` |
| Transports | TCP REALITY 443, gRPC REALITY 8443, XHTTP REALITY 2053, Trojan TLS 9443 |
| Panel and subscriptions | Caddy HTTPS on 2096, proxying to Marzban's Unix socket |
| Certificates and DNS | External ACME/DNS-01 certificate and a DuckDNS updater |

My configuration, credentials, addresses and archives remain outside Git. Removing
the old source files does not remove installed services or their dependencies.
I will use the tag and private recovery material when planning changes, rather
than rerun the archived bootstrap on my live VPS.

Earlier operating evidence is retained in the [ledger](../audit/acceptance-ledger.md).
On 2026-10-23, Caddy's served certificate was repaired by adding `--force` to its
reload command. The earlier hook had skipped an unchanged Caddyfile and continued
serving the previous certificate. The hook still restarts Marzban on renewal;
that behavior can interrupt VPN traffic and requires separate investigation.

The same audit found a legacy backup timer failing and SQLite readable by other
local accounts. Backup delivery and a fresh external recovery drill were not
established by that audit. These remain server maintenance tasks; this repository
cleanup does not resolve them.

## REALITY subscription limitation

The official Marzban v0.8.4 subscription code can omit the REALITY `sid` in the
first generated profile after application startup. The existing A-13 derivative
applies the one-line change from
[upstream PR #2036](https://github.com/Gozargah/Marzban/pull/2036), also described
in [issue #1986](https://github.com/Gozargah/Marzban/issues/1986).

I cannot replace A-13 with an official image just because the version label
matches. First I need to inspect the candidate and test the first subscription
after a cold start, repeated responses and the formats my clients consume. I'll
compare REALITY parameters privately. I can retire A-13 once those tests pass and
I have a way to restore the previous image and data.

## Historical client observations

These are observations from the legacy acceptance on 2026-07-28, not support
claims for current application releases or the new setup. Exact client/OS build
numbers are not retained in the public ledger, so I need to retest my actual versions.

| Client | TCP REALITY | gRPC REALITY | Trojan TLS | XHTTP REALITY |
| --- | --- | --- | --- | --- |
| Hiddify | Traffic confirmed | Traffic confirmed | Traffic confirmed | Not working in that test |
| Karing | Traffic confirmed | Traffic confirmed | Traffic confirmed | Not working in that test |
| V2RayTun, V2Box, Streisand, OneXray | Not confirmed | Not confirmed | Not confirmed | Not confirmed |
| Pinned Xray-core test client | Not tested | Not tested | Not tested | Server-side end-to-end check passed |

The server-side XHTTP check did not establish reachability from an external client
network. HTTP subscription checks on 2026-10-23 confirmed four generic profiles
and three supported profiles in each Hiddify/Karing response; they were not new
VPN traffic tests. The old multi-network and automatic-failover matrix was not
completed. Having several profiles in a subscription does not by itself configure
or prove automatic switching in a client.

## What I need before migrating

Before changing my server, I need an inventory, a verified external recovery
bundle and a test of the candidate in isolation. The
[recovery guide](recovery.md) explains the data that must survive.

I need to preserve the complete database, signing secret, user state, proxy
credentials, inbound assignments and Host Settings. The public subscription URLs
and validation of previously issued tokens must survive too. I'll keep the
working transport parameters until I test the relevant clients; the new guide's
default paths and ports cannot replace the old ones without that preparation.

I'll separate image replacement, transport changes, DNS, certificates and OS
cleanup so I can check each change. Two instances must not share the production
SQLite database. If a release migrates it, I need the matching data for rollback,
not only the previous image.

I will schedule the cutover separately, freeze administrative writes during the
switch and verify old subscription URLs plus client traffic before retiring
anything. I need to retain the rollback image and matching data until then.
