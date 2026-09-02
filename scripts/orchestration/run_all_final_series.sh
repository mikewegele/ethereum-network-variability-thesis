#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PY="${PY:-$ROOT/.venv/bin/python3}"
RPC="${RPC:-http://localhost:8545}"

# =========================================================
# FINAL THESIS SERIES DEFAULTS
# aligned with the plan.md / methodology target setup
# =========================================================
REPS="${REPS:-01 02 03 04 05}"
RUN_ROOT="${RUN_ROOT:-experiments/runs}"
BASELINE_REF="${BASELINE_REF:-}"

TX_RATE="${TX_RATE:-5}"
MAX_INFLIGHT="${MAX_INFLIGHT:-32}"
CHAIN_ID="${CHAIN_ID:-1337}"
BLOCK_PERIOD_S="${BLOCK_PERIOD_S:-2}"
WINDOW_S="${WINDOW_S:-60}"

# phased run structure for thesis main series
WARMUP_S="${WARMUP_S:-60}"
BASELINE_S="${BASELINE_S:-60}"
STRESS_S="${STRESS_S:-180}"
RECOVERY_S="${RECOVERY_S:-60}"

# exact scenario levels from the plan
LATENCY_LEVELS="${LATENCY_LEVELS:-0 50 100 200 400 800}"
PACKET_LOSS_LEVELS="${PACKET_LOSS_LEVELS:-0 1 3 5 10 20}"
BANDWIDTH_LEVELS="${BANDWIDTH_LEVELS:-unlimited 10mbit 1mbit 128kbit 64kbit}"
OFFLINE_LEVELS="${OFFLINE_LEVELS:-1 2}"

# combined scenarios are part of the plan, but only after single-factor series
RUN_COMBINED="${RUN_COMBINED:-0}"
COMBINED_LEVELS="${COMBINED_LEVELS:-250:1mbit 500:1mbit}"

# all main thesis series enabled by default
RUN_BASELINE="${RUN_BASELINE:-1}"
RUN_LATENCY="${RUN_LATENCY:-1}"
RUN_PACKETLOSS="${RUN_PACKETLOSS:-1}"
RUN_BANDWIDTH="${RUN_BANDWIDTH:-1}"
RUN_OFFLINE="${RUN_OFFLINE:-1}"

TOTAL_DURATION="$((WARMUP_S + BASELINE_S + STRESS_S + RECOVERY_S))"

run_mode() {
  local mode="$1"

  echo
  echo "========================================================="
  echo "FINAL THESIS SERIES MODE: $mode"
  echo "========================================================="

  PHASE_MODE=phased \
  RESET_BETWEEN_RUNS=1 \
  MODE="$mode" \
  PY="$PY" \
  RPC="$RPC" \
  REPS="$REPS" \
  RUN_ROOT="$RUN_ROOT" \
  BASELINE_REF="$BASELINE_REF" \
  TX_RATE="$TX_RATE" \
  MAX_INFLIGHT="$MAX_INFLIGHT" \
  CHAIN_ID="$CHAIN_ID" \
  BLOCK_PERIOD_S="$BLOCK_PERIOD_S" \
  WINDOW_S="$WINDOW_S" \
  WARMUP_S="$WARMUP_S" \
  BASELINE_S="$BASELINE_S" \
  STRESS_S="$STRESS_S" \
  RECOVERY_S="$RECOVERY_S" \
  LATENCY_LEVELS="$LATENCY_LEVELS" \
  PACKET_LOSS_LEVELS="$PACKET_LOSS_LEVELS" \
  BANDWIDTH_LEVELS="$BANDWIDTH_LEVELS" \
  OFFLINE_LEVELS="$OFFLINE_LEVELS" \
  COMBINED_LEVELS="$COMBINED_LEVELS" \
  DUR_COLLECT="$TOTAL_DURATION" \
  DUR_LOAD="$TOTAL_DURATION" \
  bash scripts/orchestration/run_matrix.sh
}

echo "========================================================="
echo "run_all_final_series.sh"
echo "ROOT=$ROOT"
echo "PY=$PY"
echo "RPC=$RPC"
echo "REPS=$REPS"
echo "RUN_ROOT=$RUN_ROOT"
echo "TX_RATE=$TX_RATE"
echo "MAX_INFLIGHT=$MAX_INFLIGHT"
echo "CHAIN_ID=$CHAIN_ID"
echo "BLOCK_PERIOD_S=$BLOCK_PERIOD_S"
echo "WINDOW_S=$WINDOW_S"
echo "WARMUP_S=$WARMUP_S"
echo "BASELINE_S=$BASELINE_S"
echo "STRESS_S=$STRESS_S"
echo "RECOVERY_S=$RECOVERY_S"
echo "TOTAL_DURATION=$TOTAL_DURATION"
echo "LATENCY_LEVELS=$LATENCY_LEVELS"
echo "PACKET_LOSS_LEVELS=$PACKET_LOSS_LEVELS"
echo "BANDWIDTH_LEVELS=$BANDWIDTH_LEVELS"
echo "OFFLINE_LEVELS=$OFFLINE_LEVELS"
echo "RUN_BASELINE=$RUN_BASELINE"
echo "RUN_LATENCY=$RUN_LATENCY"
echo "RUN_PACKETLOSS=$RUN_PACKETLOSS"
echo "RUN_BANDWIDTH=$RUN_BANDWIDTH"
echo "RUN_OFFLINE=$RUN_OFFLINE"
echo "RUN_COMBINED=$RUN_COMBINED"
echo "BASELINE_REF=${BASELINE_REF:-<none>}"
echo "========================================================="

if [ "$RUN_BASELINE" = "1" ]; then
  run_mode baseline
fi

if [ "$RUN_LATENCY" = "1" ]; then
  run_mode latency
fi

if [ "$RUN_PACKETLOSS" = "1" ]; then
  run_mode packetloss
fi

if [ "$RUN_BANDWIDTH" = "1" ]; then
  run_mode bandwidth
fi

if [ "$RUN_OFFLINE" = "1" ]; then
  run_mode offline
fi

if [ "$RUN_COMBINED" = "1" ]; then
  run_mode combined
fi

echo
echo "Final thesis series finished."