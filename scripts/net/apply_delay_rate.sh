#!/usr/bin/env bash
set -euo pipefail

DELAY_MS="${1:?usage: apply_delay_rate.sh <delay_ms> <rate> [burst] [latency]}"
RATE="${2:?usage: apply_delay_rate.sh <delay_ms> <rate> [burst] [latency]}"
BURST="${3:-32kb}"
TBF_LATENCY="${4:-400ms}"

for v in validator1 validator2 validator3 validator4; do
  docker run --rm --network container:$v --cap-add NET_ADMIN nicolaka/netshoot sh -lc "
    set -e

    tc qdisc del dev eth0 root >/dev/null 2>&1 || true

    tc qdisc add dev eth0 root handle 1: netem delay ${DELAY_MS}ms

    tc qdisc add dev eth0 parent 1:1 handle 10: tbf rate ${RATE} burst ${BURST} latency ${TBF_LATENCY}

    echo '--- '$v' ---'
    tc qdisc show dev eth0
  "
done
echo "applied delay=${DELAY_MS}ms + rate=${RATE} burst=${BURST} latency=${TBF_LATENCY} to all validators"