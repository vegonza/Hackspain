#!/usr/bin/env bash
set -euo pipefail

# The challenge ERP binds to loopback; expose it to the Compose network via TCP.
python /challenge/alberto_erp.py --puerto 8010 "$@" &
erp_pid=$!
socat TCP-LISTEN:8009,bind=0.0.0.0,reuseaddr,fork TCP:127.0.0.1:8010 &
proxy_pid=$!
trap 'kill "$erp_pid" "$proxy_pid" 2>/dev/null || true; wait || true' EXIT
trap 'exit 0' TERM INT
wait -n "$erp_pid" "$proxy_pid"
