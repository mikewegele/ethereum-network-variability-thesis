#!/usr/bin/env bash
set -euo pipefail

for v in validator1 validator2 validator3 validator4; do
  docker run --rm --network "container:$v" --cap-add NET_ADMIN nicolaka/netshoot sh -lc '
    tc qdisc del dev eth0 root >/dev/null 2>&1 || true

    if iptables -S OAI_NETEM >/dev/null 2>&1; then
      iptables -D OUTPUT -j OAI_NETEM >/dev/null 2>&1 || true
      iptables -D INPUT -j OAI_NETEM >/dev/null 2>&1 || true
      iptables -F OAI_NETEM >/dev/null 2>&1 || true
      iptables -X OAI_NETEM >/dev/null 2>&1 || true
    fi

    echo "cleared net rules"
  ' >/dev/null 2>&1 || true
done

echo "cleared tc and offline/disconnection rules"