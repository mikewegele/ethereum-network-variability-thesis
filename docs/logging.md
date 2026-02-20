# Logging & Observability Plan

This document defines what data is collected, how it is stored, and how metrics are derived.

## Data Sources

### 1) JSON-RPC (primary measurement channel)

We poll the JSON-RPC endpoint to collect:
- block number and block timestamps
- peer count
- IBFT validator set
- transaction receipts / inclusion

Rationale:
JSON-RPC responses are structured, easy to persist, and reproducible.

Relevant methods:
- eth_blockNumber
- eth_getBlockByNumber
- net_peerCount
- ibft_getValidatorsByBlockNumber

### 2) Client logs (supporting evidence)

Besu logs are collected per validator to:
- debug connectivity and consensus behavior
- correlate failures with warnings/timeouts
- provide qualitative evidence for stalls or recovery

Log level:
INFO by default; switch to DEBUG for debugging (not for all production runs).

### 3) Node metrics (optional but recommended)

Enable Prometheus metrics to collect runtime indicators (CPU, memory, internal metrics).
This supports explaining performance degradation vs. consensus failure.

## Storage Layout

All artifacts are stored per run:

experiments/runs/<run_id>/
- meta.json
- rpc/
    - blocks.jsonl
    - peers.jsonl
    - validators.jsonl
    - tx.jsonl
- logs/
    - validator1.log
    - validator2.log
    - validator3.log
    - validator4.log

## Run Metadata (meta.json)

meta.json includes:
- timestamp, git commit hash
- factor levels: latency, bandwidth, offline validators
- durations (warmup, measure, recovery)
- software versions (besu image tag)

## Metric Derivation

- Block time variance: derived from consecutive block timestamps
- Transaction inclusion delay: derived from tx submission time and inclusion block timestamp
- Stalled consensus: detected when no block within stall threshold and pending tx exist