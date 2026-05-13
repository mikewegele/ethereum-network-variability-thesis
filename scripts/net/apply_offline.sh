#!/usr/bin/env bash
set -euo pipefail

COUNT="${1:?usage: apply_offline.sh <count> (e.g. 1 | 2)}"

case "$COUNT" in
  1)
    TARGETS=("validator4")
    ;;
  2)
    TARGETS=("validator3" "validator4")
    ;;
  *)
    echo "ERROR: supported offline counts are 1 or 2"
    exit 1
    ;;
esac

for v in "${TARGETS[@]}"; do
  docker run --rm --network "container:$v" --cap-add NET_ADMIN nicolaka/netshoot sh -lc '
    iptables -N OAI_NETEM 2>/dev/null || true
    iptables -C OUTPUT -j OAI_NETEM 2>/dev/null || iptables -I OUTPUT 1 -j OAI_NETEM
    iptables -C INPUT -j OAI_NETEM 2>/dev/null || iptables -I INPUT 1 -j OAI_NETEM

    iptables -F OAI_NETEM

    iptables -A OAI_NETEM -p tcp --dport 30303 -j DROP
    iptables -A OAI_NETEM -p tcp --sport 30303 -j DROP
    iptables -A OAI_NETEM -p udp --dport 30303 -j DROP
    iptables -A OAI_NETEM -p udp --sport 30303 -j DROP
  '
done

echo "applied offline/disconnection to ${TARGETS[*]} (P2P traffic on port 30303 dropped)"