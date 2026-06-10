#!/usr/bin/env bash
set -euo pipefail

PARTITION="${1:?usage: apply_partition.sh <3-1|2-2>}"

VALIDATORS=("validator1" "validator2" "validator3" "validator4")

case "$PARTITION" in
  3-1)
    GROUP_A=("validator1" "validator2" "validator3")
    GROUP_B=("validator4")
    ;;
  2-2)
    GROUP_A=("validator1" "validator2")
    GROUP_B=("validator3" "validator4")
    ;;
  *)
    echo "ERROR: supported partition types are 3-1 or 2-2"
    exit 1
    ;;
esac

contains() {
  local item="$1"
  shift

  for x in "$@"; do
    if [ "$x" = "$item" ]; then
      return 0
    fi
  done

  return 1
}

peers_to_block_csv() {
  local validator="$1"

  if contains "$validator" "${GROUP_A[@]}"; then
    local IFS=","
    echo "${GROUP_B[*]}"
  else
    local IFS=","
    echo "${GROUP_A[*]}"
  fi
}

for v in "${VALIDATORS[@]}"; do
  PEERS_CSV="$(peers_to_block_csv "$v")"

  docker run --rm \
    --network "container:$v" \
    --cap-add NET_ADMIN \
    -e PEERS_CSV="$PEERS_CSV" \
    nicolaka/netshoot sh -lc '
      set -e

      iptables -N OAI_NETEM 2>/dev/null || true
      iptables -C OUTPUT -j OAI_NETEM 2>/dev/null || iptables -I OUTPUT 1 -j OAI_NETEM
      iptables -C INPUT -j OAI_NETEM 2>/dev/null || iptables -I INPUT 1 -j OAI_NETEM

      iptables -F OAI_NETEM

      IFS=","
      for peer in $PEERS_CSV; do
        peer_ip="$(getent hosts "$peer" | awk "{print \$1}" | head -n1)"

        if [ -z "$peer_ip" ]; then
          echo "ERROR: could not resolve peer $peer"
          exit 1
        fi

        iptables -A OAI_NETEM -p tcp -d "$peer_ip" --dport 30303 -j DROP
        iptables -A OAI_NETEM -p tcp -s "$peer_ip" --sport 30303 -j DROP
        iptables -A OAI_NETEM -p udp -d "$peer_ip" --dport 30303 -j DROP
        iptables -A OAI_NETEM -p udp -s "$peer_ip" --sport 30303 -j DROP
      done
    '
done

echo "applied network partition $PARTITION"
echo "group A: ${GROUP_A[*]}"
echo "group B: ${GROUP_B[*]}"
echo "blocked P2P traffic on port 30303 between groups only"