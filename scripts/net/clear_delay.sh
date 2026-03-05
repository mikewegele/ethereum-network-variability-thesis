#!/usr/bin/env bash
set -euo pipefail
for v in validator1 validator2 validator3 validator4; do
  docker run --rm --network container:$v --cap-add NET_ADMIN nicolaka/netshoot \
    tc qdisc del dev eth0 root >/dev/null 2>&1 || true
done
echo "cleared delay on all validators"
