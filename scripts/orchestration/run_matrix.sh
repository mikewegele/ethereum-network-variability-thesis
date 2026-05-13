#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PY="${PY:-$ROOT/.venv/bin/python3}"
RPC="${RPC:-http://localhost:8545}"

# =========================================================
# MODE
# baseline | bandwidth | latency | packetloss | offline | combined
# =========================================================
MODE="${MODE:-baseline}"

# =========================================================
# GENERAL RUN SETTINGS
# =========================================================
REPS_STR="${REPS:-01 02 03 04 05}"
read -r -a REPS <<< "$REPS_STR"

DUR_COLLECT="${DUR_COLLECT:-360}"
DUR_LOAD="${DUR_LOAD:-360}"
COLLECT_TIMEOUT_S="${COLLECT_TIMEOUT_S:-0}"

TX_RATE="${TX_RATE:-5}"
MAX_INFLIGHT="${MAX_INFLIGHT:-32}"
CHAIN_ID="${CHAIN_ID:-1337}"

PK="${PK:-02ac8b117de16f6ea563700605e1cec6fd378ec7a59245d95b427b1cb6a1b152}"
TO="${TO:-0xFeaF0823C5C078F1afbEF36F0B5455E70988F9D7}"

BLOCK_PERIOD_S="${BLOCK_PERIOD_S:-2}"
WINDOW_S="${WINDOW_S:-60}"

BASELINE_REF="${BASELINE_REF:-}"
RESET_BETWEEN_RUNS="${RESET_BETWEEN_RUNS:-0}"
PHASE_MODE="${PHASE_MODE:-phased}"
WARMUP_S="${WARMUP_S:-60}"
BASELINE_S="${BASELINE_S:-60}"
STRESS_S="${STRESS_S:-180}"
RECOVERY_S="${RECOVERY_S:-60}"

CHAIN_WAIT_MAX_TRIES="${CHAIN_WAIT_MAX_TRIES:-20}"
CHAIN_WAIT_SLEEP_S="${CHAIN_WAIT_SLEEP_S:-3}"
CHAIN_WAIT_MIN_DELTA="${CHAIN_WAIT_MIN_DELTA:-1}"

# =========================================================
# BANDWIDTH SETTINGS
# =========================================================
BANDWIDTH_LEVELS_STR="${BANDWIDTH_LEVELS:-unlimited 10mbit 1mbit 128kbit 64kbit}"
read -r -a BANDWIDTH_LEVELS <<< "$BANDWIDTH_LEVELS_STR"

# =========================================================
# LATENCY SETTINGS
# =========================================================
LATENCY_LEVELS_STR="${LATENCY_LEVELS:-0 50 100 200 400 800}"
read -r -a LATENCY_LEVELS <<< "$LATENCY_LEVELS_STR"

# =========================================================
# PACKET LOSS SETTINGS
# =========================================================
PACKET_LOSS_LEVELS_STR="${PACKET_LOSS_LEVELS:-0 1 3 5 10 20}"
read -r -a PACKET_LOSS_LEVELS <<< "$PACKET_LOSS_LEVELS_STR"

# =========================================================
# OFFLINE SETTINGS
# =========================================================
OFFLINE_LEVELS_STR="${OFFLINE_LEVELS:-1 2}"
read -r -a OFFLINE_LEVELS <<< "$OFFLINE_LEVELS_STR"

# =========================================================
# COMBINED SETTINGS
# format: "latency_ms:bandwidth"
# =========================================================
COMBINED_LEVELS_STR="${COMBINED_LEVELS:-250:1mbit 500:1mbit}"
read -r -a COMBINED_LEVELS <<< "$COMBINED_LEVELS_STR"

RUN_ROOT="${RUN_ROOT:-experiments/runs}"
mkdir -p "$RUN_ROOT"

echo "========================================================="
echo "run_matrix.sh"
echo "ROOT=$ROOT"
echo "PY=$PY"
echo "RPC=$RPC"
echo "MODE=$MODE"
echo "REPS=${REPS[*]}"
echo "DUR_COLLECT=$DUR_COLLECT"
echo "DUR_LOAD=$DUR_LOAD"
echo "TX_RATE=$TX_RATE"
echo "MAX_INFLIGHT=$MAX_INFLIGHT"
echo "CHAIN_ID=$CHAIN_ID"
echo "BLOCK_PERIOD_S=$BLOCK_PERIOD_S"
echo "WINDOW_S=$WINDOW_S"
echo "BASELINE_REF=${BASELINE_REF:-<none>}"
echo "RESET_BETWEEN_RUNS=$RESET_BETWEEN_RUNS"
echo "PHASE_MODE=$PHASE_MODE"
echo "WARMUP_S=$WARMUP_S"
echo "BASELINE_S=$BASELINE_S"
echo "STRESS_S=$STRESS_S"
echo "RECOVERY_S=$RECOVERY_S"
echo "LATENCY_LEVELS=${LATENCY_LEVELS[*]}"
echo "PACKET_LOSS_LEVELS=${PACKET_LOSS_LEVELS[*]}"
echo "BANDWIDTH_LEVELS=${BANDWIDTH_LEVELS[*]}"
echo "OFFLINE_LEVELS=${OFFLINE_LEVELS[*]}"
echo "COMBINED_LEVELS=${COMBINED_LEVELS[*]}"
echo "CHAIN_WAIT_MAX_TRIES=$CHAIN_WAIT_MAX_TRIES"
echo "CHAIN_WAIT_SLEEP_S=$CHAIN_WAIT_SLEEP_S"
echo "CHAIN_WAIT_MIN_DELTA=$CHAIN_WAIT_MIN_DELTA"
echo "========================================================="

cleanup() {
  bash scripts/net/clear_net.sh >/dev/null 2>&1 || true
  if [ -n "${COLLECT_PID:-}" ]; then
    kill "$COLLECT_PID" >/dev/null 2>&1 || true
    wait "$COLLECT_PID" >/dev/null 2>&1 || true
  fi
  if [ -n "${LOAD_PID:-}" ]; then
    kill "$LOAD_PID" >/dev/null 2>&1 || true
    wait "$LOAD_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

timestamp() {
  date +%F_%H-%M-%S
}

get_block_number() {
  local payload='{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
  curl -fsS -X POST "$RPC" -H 'Content-Type: application/json' --data "$payload" \
    | "$PY" -c 'import json,sys; data=json.load(sys.stdin); r=data.get("result"); print(int(r,16) if r else "")' \
    2>/dev/null || true
}

write_run_scenario_meta() {
  local run_dir="$1"
  cat > "$run_dir/scenario_meta.json" <<EOF
{
  "mode": "$MODE",
  "phase_mode": "$PHASE_MODE",
  "warmup_s": $WARMUP_S,
  "baseline_s": $BASELINE_S,
  "stress_s": $STRESS_S,
  "recovery_s": $RECOVERY_S,
  "block_period_s": $BLOCK_PERIOD_S,
  "window_s": $WINDOW_S,
  "tx_rate": $TX_RATE,
  "max_inflight": $MAX_INFLIGHT
}
EOF
}

apply_net_mode() {
  local mode="$1"
  local level="$2"

  bash scripts/net/clear_net.sh >/dev/null 2>&1 || true

  case "$mode" in
    baseline)
      echo "Applying baseline network (no impairment)"
      ;;

    bandwidth)
      if [ "$level" = "unlimited" ]; then
        echo "Applying bandwidth=unlimited"
      else
        echo "Applying bandwidth=$level"
        bash scripts/net/apply_rate.sh "$level"
      fi
      ;;

    latency)
      if [ "$level" = "0" ]; then
        echo "Applying latency=0ms"
      else
        echo "Applying latency=${level}ms"
        bash scripts/net/apply_delay.sh "$level"
      fi
      ;;

    packetloss)
      if [ "$level" = "0" ] || [ "$level" = "0.0" ]; then
        echo "Applying packet loss=0%"
      else
        echo "Applying packet loss=${level}%"
        bash scripts/net/apply_loss.sh "$level"
      fi
      ;;

    offline)
      echo "Applying offline validators count=$level"
      bash scripts/net/apply_offline.sh "$level"
      ;;

    combined)
      local delay_ms="${level%%:*}"
      local bw="${level##*:}"

      if [ -z "$delay_ms" ] || [ -z "$bw" ] || [ "$delay_ms" = "$level" ]; then
        echo "ERROR: combined level must look like 250:1mbit"
        exit 1
      fi

      echo "Applying combined latency=${delay_ms}ms bandwidth=${bw}"
      if [ "$bw" != "unlimited" ]; then
        bash scripts/net/apply_rate.sh "$bw"
      fi
      if [ "$delay_ms" != "0" ]; then
        bash scripts/net/apply_delay.sh "$delay_ms"
      fi
      ;;

    *)
      echo "ERROR: unknown mode '$mode'"
      exit 1
      ;;
  esac
}

backfill_blocks_if_missing() {
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
  "$PY" scripts/collect/fetch_blocks_range.py \
    --rpc "$RPC" \
    --out "$blocks" \
    --start "$start" \
    --end "$end"
}

wait_chain_is_advancing() {
  echo "Waiting for chain to advance..."

  local tries=0
  local a=""
  local b=""
  local delta=""

  while [ "$tries" -lt "$CHAIN_WAIT_MAX_TRIES" ]; do
    a="$(get_block_number)"
    if [ -z "${a:-}" ]; then
      tries=$((tries + 1))
      echo "WARN: RPC not ready yet (try $tries/$CHAIN_WAIT_MAX_TRIES)"
      sleep "$CHAIN_WAIT_SLEEP_S"
      continue
    fi

    sleep "$CHAIN_WAIT_SLEEP_S"

    b="$(get_block_number)"
    if [ -z "${b:-}" ]; then
      tries=$((tries + 1))
      echo "WARN: RPC became unavailable while waiting (try $tries/$CHAIN_WAIT_MAX_TRIES)"
      sleep "$CHAIN_WAIT_SLEEP_S"
      continue
    fi

    delta=$((b - a))
    echo "blockNumber $a -> $b"

    if [ "$delta" -ge "$CHAIN_WAIT_MIN_DELTA" ]; then
      return 0
    fi

    tries=$((tries + 1))
  done

  echo "ERROR: chain did not advance after $CHAIN_WAIT_MAX_TRIES checks."
  echo "Last observed blockNumber: ${b:-<none>}"
  return 1
}

run_analysis() {
  local run_dir="$1"
  local analysis_offset="0"

  if [ "$PHASE_MODE" = "phased" ]; then
    analysis_offset="$WARMUP_S"
  fi

  if [ -n "${BASELINE_REF:-}" ]; then
    "$PY" scripts/analysis/analyze_run.py \
      --run "$run_dir" \
      --baseline_run "$BASELINE_REF" \
      --block_period_s "$BLOCK_PERIOD_S" \
      --window_s "$WINDOW_S" \
      --analysis_start_offset_s "$analysis_offset" \
      --phase_mode "$PHASE_MODE" \
      --warmup_s "$WARMUP_S" \
      --baseline_s "$BASELINE_S" \
      --stress_s "$STRESS_S" \
      --recovery_s "$RECOVERY_S" \
      > "$run_dir/summary.json" || true
  else
    "$PY" scripts/analysis/analyze_run.py \
      --run "$run_dir" \
      --block_period_s "$BLOCK_PERIOD_S" \
      --window_s "$WINDOW_S" \
      --analysis_start_offset_s "$analysis_offset" \
      --phase_mode "$PHASE_MODE" \
      --warmup_s "$WARMUP_S" \
      --baseline_s "$BASELINE_S" \
      --stress_s "$STRESS_S" \
      --recovery_s "$RECOVERY_S" \
      > "$run_dir/summary.json" || true
  fi
}

total_run_duration() {
  if [ "$PHASE_MODE" = "phased" ]; then
    echo $((WARMUP_S + BASELINE_S + STRESS_S + RECOVERY_S))
  else
    echo "$DUR_COLLECT"
  fi
}

reset_network_if_enabled() {
  if [ "$RESET_BETWEEN_RUNS" != "1" ]; then
    return 0
  fi

  echo "Resetting network for a clean run..."
  bash scripts/orchestration/reset_network.sh
  wait_chain_is_advancing
}

run_phased_protocol() {
  local mode="$1"
  local level="$2"
  local total_duration="$3"
  local run_dir="$4"

  if [ "$total_duration" -le 0 ]; then
    echo "ERROR: phased total duration must be > 0"
    exit 1
  fi

  if [ "$STRESS_S" -le 0 ]; then
    echo "ERROR: STRESS_S must be > 0 in phased mode"
    exit 1
  fi

  COLLECT_PID=""
  LOAD_PID=""

  "$PY" scripts/collect/collect_rpc.py \
    --rpc "$RPC" \
    --out "$run_dir" \
    --duration "$total_duration" &
  COLLECT_PID=$!

  "$PY" scripts/load/send_raw_tx_load.py \
    --rpc "$RPC" \
    --pk "$PK" \
    --to "$TO" \
    --rate "$TX_RATE" \
    --duration_s "$total_duration" \
    --chain_id "$CHAIN_ID" \
    --max_inflight "$MAX_INFLIGHT" &
  LOAD_PID=$!

  echo "Phase 1/4: Warm-up (${WARMUP_S}s)"
  sleep "$WARMUP_S"

  echo "Phase 2/4: Baseline (${BASELINE_S}s)"
  sleep "$BASELINE_S"

  echo "Phase 3/4: Stress (${STRESS_S}s)"
  apply_net_mode "$mode" "$level"

  if ! wait_chain_is_advancing; then
    if [ "$mode" = "offline" ] && [ "$level" = "2" ]; then
      echo "INFO: no chain progress under offline=2 is expected; continuing stress phase."
    else
      echo "WARN: chain did not advance after applying impairment; continuing stress phase."
    fi
  fi

  sleep "$STRESS_S"

  echo "Phase 4/4: Recovery (${RECOVERY_S}s)"
  bash scripts/net/clear_net.sh >/dev/null 2>&1 || true

  if ! wait_chain_is_advancing; then
    echo "WARN: chain did not resume immediately after impairment removal; continuing recovery phase."
  fi

  sleep "$RECOVERY_S"

  wait "$LOAD_PID" || true
  COLLECT_PID=""
  LOAD_PID=""
}

run_one() {
  local mode="$1"
  local level="$2"
  local rep="$3"

  local label
  case "$mode" in
    baseline)   label="baseline" ;;
    bandwidth)  label="bw_${level}" ;;
    latency)    label="lat_${level}ms" ;;
    packetloss) label="loss_${level}pct" ;;
    offline)    label="offline_${level}" ;;
    combined)
      local delay_ms="${level%%:*}"
      local bw="${level##*:}"
      label="combined_${delay_ms}ms_${bw}"
      ;;
    *)          label="misc_${level}" ;;
  esac

  local run_dir="$RUN_ROOT/$mode/$(timestamp)_${label}_rep${rep}"
  mkdir -p "$run_dir"
  write_run_scenario_meta "$run_dir"

  echo
  echo "========================================================="
  echo "RUN"
  echo "mode=$mode"
  echo "level=$level"
  echo "rep=$rep"
  echo "dir=$run_dir"
  echo "========================================================="

  reset_network_if_enabled

  if [ "$PHASE_MODE" = "phased" ]; then
    local total_duration
    total_duration="$(total_run_duration)"
    echo "Using phased protocol with total_duration=${total_duration}s"
    run_phased_protocol "$mode" "$level" "$total_duration" "$run_dir"
  else
    apply_net_mode "$mode" "$level"
    wait_chain_is_advancing

    COLLECT_PID=""
    "$PY" scripts/collect/collect_rpc.py \
      --rpc "$RPC" \
      --out "$run_dir" \
      --duration "$DUR_COLLECT" &
    COLLECT_PID=$!

    "$PY" scripts/load/send_raw_tx_load.py \
      --rpc "$RPC" \
      --pk "$PK" \
      --to "$TO" \
      --rate "$TX_RATE" \
      --duration_s "$DUR_LOAD" \
      --chain_id "$CHAIN_ID" \
      --max_inflight "$MAX_INFLIGHT" || true

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
  fi

  bash scripts/net/clear_net.sh >/dev/null 2>&1 || true

  backfill_blocks_if_missing "$run_dir"
  run_analysis "$run_dir"

  echo "--- summary ---"
  cat "$run_dir/summary.json" || true

  sleep 5
}

main() {
  if [ "$RESET_BETWEEN_RUNS" = "1" ]; then
    echo "RESET_BETWEEN_RUNS=1 -> skipping initial RPC wait, first run will reset the network."
  else
    wait_chain_is_advancing
  fi

  case "$MODE" in
    baseline)
      for rep in "${REPS[@]}"; do
        run_one baseline baseline "$rep"
      done
      ;;
    bandwidth)
      for level in "${BANDWIDTH_LEVELS[@]}"; do
        for rep in "${REPS[@]}"; do
          run_one bandwidth "$level" "$rep"
        done
      done
      ;;
    latency)
      for level in "${LATENCY_LEVELS[@]}"; do
        for rep in "${REPS[@]}"; do
          run_one latency "$level" "$rep"
        done
      done
      ;;
    packetloss)
      for level in "${PACKET_LOSS_LEVELS[@]}"; do
        for rep in "${REPS[@]}"; do
          run_one packetloss "$level" "$rep"
        done
      done
      ;;
    offline)
      for level in "${OFFLINE_LEVELS[@]}"; do
        for rep in "${REPS[@]}"; do
          run_one offline "$level" "$rep"
        done
      done
      ;;
    combined)
      for level in "${COMBINED_LEVELS[@]}"; do
        for rep in "${REPS[@]}"; do
          run_one combined "$level" "$rep"
        done
      done
      ;;
    *)
      echo "ERROR: unsupported MODE='$MODE'"
      echo "Use one of: baseline | bandwidth | latency | packetloss | offline | combined"
      exit 1
      ;;
  esac

  echo
  echo "ALL DONE"
}

main