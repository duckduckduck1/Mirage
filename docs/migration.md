# Migration and troubleshooting

[Back to README](../README.md)

## Existing deployment and archive

The repository now describes a new upstream-only setup. The running VPS has not
been converted to it. The former deployment source is preserved at
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

Configuration, credentials, addresses and archives remain outside Git. Removing
their old source files from this branch does not remove installed services or
make the server independent of them. Consult the tag and protected recovery
material when planning changes; do not rerun the archived bootstrap on a live VPS.

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

Do not replace the working derivative with an official image solely because the
version label matches. Check the candidate's actual code/release and test the
first subscription response after a cold start, repeated responses, and the
formats consumed by the real clients. Compare their REALITY parameters without
printing keys, UUIDs or subscription contents. Retire A-13 only after that test
passes and the migration has its own rollback plan.

## Historical client observations

These are observations from the legacy acceptance on 2026-07-28, not support
claims for current application releases or the new setup. Exact client/OS build
numbers are not retained in the public ledger, so retest the actual versions.

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

## Requirements for a later migration

Before any live change, inventory the actual deployment and obtain a fresh,
verified external recovery bundle. Rehearse the candidate in isolation. The
[recovery guide](recovery.md) explains the data that must survive.

Preserve the complete database, signing secret, user creation/revocation state,
proxy credentials, inbound tags/assignments and Host Settings. Preserve the public
subscription URL and the old endpoint's ability to validate previously issued
tokens. Keep working transport parameters until the relevant clients have been
tested. A new fresh-install default path cannot silently replace the old one.

Do not combine image replacement, transport changes, DNS changes, certificate
management changes and OS cleanup into a single untested switch. Never run two
instances on the production SQLite database. A database migration requires a
matching data rollback, not only the previous image.

Authorize the eventual cutover separately, freeze administrative writes during
the switch, and verify old subscription URLs plus client traffic before retiring
anything. Keep the rollback image and matching state until acceptance is complete.

## Troubleshooting

Record incident time and timezone, affected network, client/OS versions, selected
profile, duration and whether other users were affected. Redact infrastructure
addresses, request URLs and credentials before sharing evidence.

| Symptom | Next useful check |
| --- | --- |
| All users lose traffic together | Application/core restarts, certificate hooks, VPS reboot, memory and disk events |
| Only one network fails | Same client/profile on another network, then simultaneous client/server observation |
| Subscriptions fail but a cached profile works | Public HTTPS certificate, subscription endpoint and proxy/socket state |
| One client fails | Its actual core, supported transport, import format, routing and TUN behavior |
| First REALITY import fails after a restart | Generated `sid` and the candidate image's subscription implementation |

A TCP handshake confirms that a connection reached a listener; it does not prove
a successful TLS/REALITY handshake or a usable tunnel. A generic TLS probe is not
a replacement for a correctly configured REALITY client. Determine whether the
server receives the request, sends a response and whether that response reaches
the client before assigning the failure to an ISP or server firewall.

Multiple ports on one address share the address and route as failure points.
Changing DNS does not alter an IP-literal profile's destination, and adding a
domain does not guarantee a different path. Protocol choices require actual
network tests; this repository does not promise a universal bypass for Russia
or any other network.
