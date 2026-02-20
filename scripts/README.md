# Scripts Overview

## collect_rpc.sh (or collect_rpc.py)

Polls JSON-RPC and writes JSONL files:
- blocks.jsonl
- peers.jsonl
- validators.jsonl

## collect_logs.sh

Exports docker logs per validator into experiments/runs/<run_id>/logs/

## analyze.py

Reads JSONL artifacts and produces:
- summary.csv
- plots (optional)
- stall events