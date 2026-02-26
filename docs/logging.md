# Logging & Observability Plan

This document defines what data is collected, how it is stored, and how metrics are derived.

The goal is to enable reproducible and transparent measurement of performance degradation and consensus stability.

---

## Data Sources

### 1) JSON-RPC (Primary Measurement Channel)

We poll the JSON-RPC endpoint to collect:

- block number
- block timestamps
- peer count
- IBFT validator set
- transaction receipts / inclusion

Rationale:

JSON-RPC responses are structured, deterministic, and reproducible.
Block timestamps provide the primary signal for consensus progress.

Relevant methods:

- eth_blockNumber
- eth_getBlockByNumber
- net_peerCount
- ibft_getValidatorsByBlockNumber

Primary liveness indicator:

- inter-block time
- chain growth rate (CGR)

---

### 2) Client Logs (Supporting Evidence)

Besu logs are collected per validator to:

- debug connectivity and consensus behavior
- observe timeout escalation
- correlate round changes with inter-block gaps
- validate stall classification

Log level:

- INFO for standard runs
- DEBUG only for targeted debugging

Logs are not used as primary metrics but serve as qualitative validation.

---

### 3) Node Metrics (Optional but Recommended)

Prometheus metrics may be enabled to collect:

- CPU usage
- memory usage
- networking statistics
- internal consensus indicators (if exposed)

Purpose:

Distinguish resource exhaustion from consensus-level instability.

---

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

This structure enables full offline re-analysis.

---

## Run Metadata (meta.json)

meta.json includes:

- timestamp
- git commit hash
- factor levels (latency, bandwidth, offline validators)
- durations (warmup, measure, recovery)
- software versions (Besu image tag)
- baseline reference (if applicable)

---

## Metric Derivation

### Block Time

Derived from consecutive block timestamps:

block_time_i = timestamp(block_i) - timestamp(block_{i-1})

Used to compute:

- mean
- variance
- maximum inter-block gap

---

### Baseline Reference

From the baseline run:

T_baseline = median(block_time_baseline)

This value serves as reference for stall classification.

---

### Chain Growth Rate (CGR)

For observation window W (default: 60 seconds):

CGR(W) = number_of_blocks_in_window / W

Purpose:

- continuous consensus progress indicator
- detect near-stalled execution
- distinguish gradual slowdown from breakdown

---

### Stalled Consensus (Operational Detection)

Consensus is operationally classified as stalled if:

block_time ≥ T_stall

where:

T_stall = k × T_baseline

with k ∈ {3, 4, 5, 6}

Sensitivity analysis across k values ensures robustness of classification.

Additionally, sustained near-zero CGR over the observation window is treated as strong evidence of stalled execution.

---

### Transaction Inclusion Delay

Derived from:

tx_delay = timestamp(block_including_tx) - timestamp(tx_submission)

Purpose:

- quantify user-visible degradation
- detect backlog formation under stress

---

### Peer Connectivity

Derived from:

net_peerCount

Purpose:

- validate network partition scenarios
- correlate connectivity drops with stall events
- distinguish quorum violation from timing instability