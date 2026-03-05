#!/usr/bin/env bash
set -euo pipefail

RATE="${1:?usage: apply_rate.sh <rate> (e.g. 10mbit | 1mbit | 128kbit)}"
BURST="${2:-32kb}"
LATENCY="${3:-400ms}"

for v in validator1 validator2 validator3 validator4; do
  docker run --rm --network container:$v --cap-add NET_ADMIN nicolaka/netshoot sh -lc "
    tc qdisc replace dev eth0 root handle 1: prio

    tc qdisc replace dev eth0 parent 1:3 handle 30: tbf \
      rate ${RATE} burst ${BURST} latency ${LATENCY}

    tc filter replace dev eth0 protocol ip parent 1:0 prio 3 u32 \
      match ip dport 30303 0xffff flowid 1:3
  "
done

echo "applied P2P rate=${RATE} (port 30303 only)"