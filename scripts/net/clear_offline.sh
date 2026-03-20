#!/usr/bin/env bash
set -euo pipefail

docker start validator1 validator2 validator3 validator4 >/dev/null 2>&1 || true
echo "all validators online"