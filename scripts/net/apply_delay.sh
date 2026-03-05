#!/usr/bin/env bash
set -euo pipefail
DELAY_MS="${1:-100}"
for v in validator1 validator2 validator3 validator4; do
  docker run --rm --network container:$v --cap-add NET_ADMIN nicolaka/netshoot \
    tc qdisc replace dev eth0 root netem delay "${DELAY_MS}ms"
done
echo "applied delay=${DELAY_MS}ms to all validators"
