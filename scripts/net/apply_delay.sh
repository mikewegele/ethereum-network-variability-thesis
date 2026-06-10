#!/usr/bin/env bash
set -euo pipefail

DELAY="${1:?usage: apply_delay.sh <delay_ms> [variation_ms] [distribution]}"
VARIATION="${2:-0}"
DISTRIBUTION="${3:-normal}"

for v in validator1 validator2 validator3 validator4; do
  if [ "$VARIATION" = "0" ] || [ "$VARIATION" = "0ms" ]; then
    NETEM_CMD="tc qdisc replace dev eth0 parent 1:3 handle 30: netem delay ${DELAY}ms"
  else
    NETEM_CMD="tc qdisc replace dev eth0 parent 1:3 handle 30: netem delay ${DELAY}ms ${VARIATION}ms distribution ${DISTRIBUTION}"
  fi

  docker run --rm --network "container:$v" --cap-add NET_ADMIN nicolaka/netshoot sh -lc "
    tc qdisc replace dev eth0 root handle 1: prio
    \$NETEM_CMD
    tc filter replace dev eth0 protocol ip parent 1:0 prio 3 u32 \
      match ip dport 30303 0xffff flowid 1:3
  "
done

if [ "$VARIATION" = "0" ] || [ "$VARIATION" = "0ms" ]; then
  echo "applied P2P delay=${DELAY}ms (port 30303 only)"
else
  echo "applied P2P delay=${DELAY}ms variation=${VARIATION}ms distribution=${DISTRIBUTION} (port 30303 only)"
fi