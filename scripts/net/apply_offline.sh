#!/usr/bin/env bash
set -euo pipefail

N="${1:-1}"

case "$N" in
  0)
    echo "no validator taken offline"
    ;;
  1)
    docker stop validator4 >/dev/null
    echo "validator4 offline"
    ;;
  2)
    docker stop validator3 validator4 >/dev/null
    echo "validator3 validator4 offline"
    ;;
  *)
    echo "Unsupported offline level: $N"
    echo "Use: 0 | 1 | 2"
    exit 1
    ;;
esac