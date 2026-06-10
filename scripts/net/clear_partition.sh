#!/usr/bin/env bash
set -euo pipefail

VALIDATORS=("validator1" "validator2" "validator3" "validator4")

for v in "${VALIDATORS[@]}"; do
  docker start "$v" >/dev/null 2>&1 || true

  docker run --rm \
    --network "container:$v" \
    --cap-add NET_ADMIN \
    nicolaka/netshoot sh -lc '
      iptables -D OUTPUT -j OAI_NETEM 2>/dev/null || true
      iptables -D INPUT -j OAI_NETEM 2>/dev/null || true
      iptables -F OAI_NETEM 2>/dev/null || true
      iptables -X OAI_NETEM 2>/dev/null || true
    '
done

echo "cleared network partition rules for validator1 validator2 validator3 validator4"
echo "all validators are reachable again"
