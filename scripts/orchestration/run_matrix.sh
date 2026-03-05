#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PY="${PY:-$ROOT/.venv/bin/python3}"
RPC="${RPC:-http://localhost:8545}"

# Which experiment kind? (affects output folder)
EXP_KIND="${EXP_KIND:-rate}"   # rate | delay | offline | misc

# Matrix (space-separated env overrides supported)
RATES_STR="${RATES:-unlimited 10mbit 1mbit 128kbit}"
REPS_STR="${REPS:-01 02 03}"
read -r -a RATES <<< "$RATES_STR"
read -r -a REPS  <<< "$REPS_STR"

# Durations
DUR_COLLECT="${DUR_COLLECT:-600}"
DUR_LOAD="${DUR_LOAD:-540}"

# Hard timeout for collector (prevents "stuck forever")
COLLECT_TIMEOUT_S="${COLLECT_TIMEOUT_S:-0}"   # 0 = off

# Load
TX_RATE="${TX_RATE:-20}"
MAX_INFLIGHT="${MAX_INFLIGHT:-256}"
PK="${PK:-02ac8b117de16f6ea563700605e1cec6fd378ec7a59245d95b427b1cb6a1b152}"
TO="${TO:-0xFeaF0823C5C078F1afbEF36F0B5455E70988F9D7}"

# Analysis
BASE="${BASE:-experiments/runs/baseline/2026-02-27_baseline_01}"
BLOCK_PERIOD_S="${BLOCK_PERIOD_S:-2}"
WINDOW_S="${WINDOW_S:-60}"

mkdir -p "experiments/runs/$EXP_KIND"

echo "PY=$PY"
echo "RPC=$RPC"
echo "BASE=$BASE"
echo "EXP_KIND=$EXP_KIND"
echo "RATES=${RATES[*]}"
echo "REPS=${REPS[*]}"
echo "DUR_COLLECT=$DUR_COLLECT DUR_LOAD=$DUR_LOAD TX_RATE=$TX_RATE MAX_INFLIGHT=$MAX_INFLIGHT"
echo "COLLECT_TIMEOUT_S=$COLLECT_TIMEOUT_S"

cleanup() {
  bash scripts/net/clear_rate.sh >/dev/null 2>&1 || true
  if [ -n "${COLLECT_PID:-}" ]; then
    kill "$COLLECT_PID" >/dev/null 2>&1 || true
    wait "$COLLECT_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

apply_rate_wrap () {
  local r="$1"
  if [ "$r" = "unlimited" ]; then
    bash scripts/net/clear_rate.sh >/dev/null
  else
    bash scripts/net/apply_rate.sh "$r" >/dev/null
  fi
}

backfill_blocks_if_missing () {
  local run_dir="$1"
  local meta="$run_dir/rpc/run_meta.json"
  local blocks="$run_dir/rpc/blocks.jsonl"

  if [ -s "$blocks" ]; then
    return 0
  fi
  if [ ! -f "$meta" ]; then
    echo "WARN: no run_meta.json -> cannot backfill blocks"
    return 0
  fi

  local start end
  start="$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1])).get("start_blockNumber",""))' "$meta")"
  end="$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1])).get("end_blockNumber",""))' "$meta")"

  if [ -z "$start" ] || [ -z "$end" ] || [ "$start" = "None" ] || [ "$end" = "None" ]; then
    echo "WARN: meta missing start/end -> cannot backfill"
    return 0
  fi

  echo "blocks.jsonl missing -> backfill $start..$end"
  rm -f "$blocks"
  "$PY" scripts/collect/fetch_blocks_range.py --rpc "$RPC" --out "$blocks" --start "$start" --end "$end"
}

wait_chain_is_advancing () {
  echo "Waiting for chain to advance..."
  local a b
  a="$(curl -s -X POST "$RPC" -H 'Content-Type: application/json' \
    --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
    | "$PY" -c 'import json,sys; print(int(json.load(sys.stdin)["result"],16))')"

  sleep 3

  b="$(curl -s -X POST "$RPC" -H 'Content-Type: application/json' \
    --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
    | "$PY" -c 'import json,sys; print(int(json.load(sys.stdin)["result"],16))')"

  echo "blockNumber $a -> $b"
  if [ "$b" -le "$a" ]; then
    echo "WARN: chain did not advance (yet). Continuing anyway."
  fi
}

wait_chain_is_advancing

for rate in "${RATES[@]}"; do
  for rep in "${REPS[@]}"; do
    RUN_DIR="experiments/runs/$EXP_KIND/$(date +%F)_${EXP_KIND}_${rate}_rep${rep}"
    mkdir -p "$RUN_DIR"

    echo
    echo "=== RUN kind=$EXP_KIND rate=$rate rep=$rep dir=$RUN_DIR ==="

    apply_rate_wrap "$rate"

    COLLECT_PID=""
    caffeinate -is "$PY" scripts/collect/collect_rpc.py --rpc "$RPC" --out "$RUN_DIR" --duration "$DUR_COLLECT" &
    COLLECT_PID=$!

    "$PY" scripts/load/send_raw_tx_load.py \
      --rpc "$RPC" \
      --pk "$PK" \
      --to "$TO" \
      --rate "$TX_RATE" \
      --max_inflight "$MAX_INFLIGHT" \
      --duration_s "$DUR_LOAD" || true

    if [ "$COLLECT_TIMEOUT_S" -gt 0 ]; then
      if ! timeout "$COLLECT_TIMEOUT_S" bash -lc "wait $COLLECT_PID"; then
        echo "WARN: collect_rpc timed out after ${COLLECT_TIMEOUT_S}s -> killing collector"
        kill "$COLLECT_PID" >/dev/null 2>&1 || true
        wait "$COLLECT_PID" >/dev/null 2>&1 || true
      fi
    else
      wait "$COLLECT_PID" || true
    fi
    COLLECT_PID=""

    bash scripts/net/clear_rate.sh >/dev/null 2>&1 || true

    backfill_blocks_if_missing "$RUN_DIR"

    "$PY" scripts/analysis/analyze_run.py \
      --run "$RUN_DIR" \
      --baseline_run "$BASE" \
      --block_period_s "$BLOCK_PERIOD_S" \
      --window_s "$WINDOW_S" \
      > "$RUN_DIR/summary.json" || true

    echo "--- summary ---"
    cat "$RUN_DIR/summary.json" || true

    sleep 5
  done
done

echo
echo "ALL DONE"