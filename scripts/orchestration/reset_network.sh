#!/usr/bin/env bash
set -euo pipefail

echo "== reset_network =="

GENESIS="ibftOutput/genesis.json"
KEYS_DIR="ibftOutput/keys"

echo "Stopping network..."
docker compose down -v >/dev/null 2>&1 || true

echo "Cleaning validator data..."
rm -rf nodes/validator1/data nodes/validator2/data nodes/validator3/data nodes/validator4/data
mkdir -p nodes/validator1/data nodes/validator2/data nodes/validator3/data nodes/validator4/data

echo "Using:"
echo "  GENESIS=$GENESIS"
echo "  KEYS=$KEYS_DIR"

if [ ! -f "$GENESIS" ]; then
  echo "ERROR: missing genesis: $GENESIS" >&2
  exit 1
fi

if [ ! -d "$KEYS_DIR" ]; then
  echo "ERROR: missing keys dir: $KEYS_DIR" >&2
  exit 1
fi

echo "Copying genesis to config/genesis.json ..."
mkdir -p config
cp "$GENESIS" config/genesis.json

echo "Restoring validator keys (from address folders)..."

# Collect key files: ibftOutput/keys/<something>/key
KEY_FILES="$(find "$KEYS_DIR" -mindepth 2 -maxdepth 2 -type f -name key | sort)"

COUNT="$(printf "%s\n" "$KEY_FILES" | sed '/^\s*$/d' | wc -l | tr -d ' ')"
if [ "$COUNT" -lt 4 ]; then
  echo "ERROR: expected at least 4 key files under $KEYS_DIR, found $COUNT" >&2
  echo "$KEY_FILES" >&2
  exit 1
fi

i=1
printf "%s\n" "$KEY_FILES" | sed '/^\s*$/d' | while IFS= read -r kf; do
  if [ "$i" -le 4 ]; then
    cp "$kf" "nodes/validator${i}/data/key"
    chmod 600 "nodes/validator${i}/data/key" || true
  fi
  i=$((i+1))
done

echo "Starting validator1..."
docker compose up -d --force-recreate validator1

# Wait until validator1 exists and has an IP
for _ in $(seq 1 30); do
  V1_IP="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' validator1 2>/dev/null || true)"
  [ -n "${V1_IP:-}" ] && break
  sleep 0.5
done

if [ -z "${V1_IP:-}" ]; then
  echo "ERROR: could not get validator1 container IP" >&2
  docker ps -a | grep validator1 || true
  exit 1
fi

# Wait until Enode URL appears in logs (or container dies)
NODEID=""
for _ in $(seq 1 60); do
  # if container exited, stop early and show logs
  if ! docker ps --format '{{.Names}}' | grep -q '^validator1$'; then
    echo "ERROR: validator1 is not running (exited). Last logs:" >&2
    docker logs --tail 120 validator1 || true
    exit 1
  fi

  NODEID="$(docker logs validator1 2>/dev/null | grep -m 1 "Enode URL" | sed -E 's/.*enode:\/\/([0-9a-fA-F]+)@.*/\1/' || true)"
  [ -n "${NODEID:-}" ] && break
  sleep 0.5
done

if [ -z "${NODEID:-}" ]; then
  echo "ERROR: could not read validator1 Enode from logs (timeout). Last logs:" >&2
  docker logs --tail 200 validator1 || true
  exit 1
fi

BOOTNODE_ENODE="enode://${NODEID}@${V1_IP}:30303"
echo "BOOTNODE_ENODE=$BOOTNODE_ENODE" > .env
echo "Wrote .env with BOOTNODE_ENODE=$BOOTNODE_ENODE"

echo "Starting validator2-4..."
docker compose up -d --force-recreate validator2 validator3 validator4

echo "Done."