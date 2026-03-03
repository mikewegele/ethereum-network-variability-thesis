#!/usr/bin/env bash
set -euo pipefail

RATE="${1:?usage: apply_rate.sh <rate> (e.g. 10mbit | 1mbit | 128kbit)}"
BURST="${2:-32kb}"
LATENCY="${3:-400ms}"

for v in validator1 validator2 validator3 validator4; do
  docker run --rm --network container:$v --cap-add NET_ADMIN nicolaka/netshoot \
    sh -lc "tc qdisc replace dev eth0 root tbf rate ${RATE} burst ${BURST} latency ${LATENCY}"
done

echo "applied rate=${RATE} burst=${BURST} latency=${LATENCY} to all validators"