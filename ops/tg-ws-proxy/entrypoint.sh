#!/bin/sh
set -eu

if [ -z "${TG_WS_SECRET:-}" ]; then
  echo "TG_WS_SECRET is required" >&2
  exit 1
fi

set -- \
  --host "${TG_WS_LISTEN_HOST:-0.0.0.0}" \
  --port "${TG_WS_LISTEN_PORT:-1443}" \
  --secret "${TG_WS_SECRET}"

if [ -n "${TG_WS_DC_IPS:-}" ]; then
  old_ifs="$IFS"
  IFS=","
  for dc_ip in $TG_WS_DC_IPS; do
    IFS="$old_ifs"
    dc_ip="$(printf '%s' "$dc_ip" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    if [ -n "$dc_ip" ]; then
      set -- "$@" --dc-ip "$dc_ip"
    fi
    IFS=","
  done
  IFS="$old_ifs"
fi

if [ "${TG_WS_NO_CFPROXY:-false}" = "true" ]; then
  set -- "$@" --no-cfproxy
fi

if [ -n "${TG_WS_FAKE_TLS_DOMAIN:-}" ]; then
  set -- "$@" --fake-tls-domain "$TG_WS_FAKE_TLS_DOMAIN"
fi

if [ "${TG_WS_VERBOSE:-false}" = "true" ]; then
  set -- "$@" --verbose
fi

exec tg-ws-proxy "$@"
