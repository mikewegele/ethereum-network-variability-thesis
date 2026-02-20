# Analysis Plan

This document defines how experimental data is aggregated, analyzed, and visualized to test the research hypotheses.

---

## Objectives

The analysis aims to:

- quantify performance degradation under network stress
- detect consensus liveness failures
- identify robustness boundaries
- compare single-factor and combined stress effects

---

## Data Aggregation

For each run:

- compute per-block statistics
- compute per-transaction statistics
- detect stall events
- store summary in a structured results file

Output:

experiments/results/<run_id>/summary.json

---

## Derived Metrics

### Block Time Statistics

From blocks.jsonl:

- mean block time
- block time variance
- block time standard deviation

Purpose:

Detect timing instability and gradual degradation.

---

### Transaction Inclusion Statistics

From tx.jsonl:

- mean inclusion delay
- median inclusion delay
- 95th percentile inclusion delay

Purpose:

Capture user-visible performance impact.

---

### Stall Indicators

From block observations:

- stall_event_count
- total_stall_duration
- time_to_first_stall

Purpose:

Detect liveness failures and robustness limits.

---

## Aggregation Across Repetitions

For each configuration (Lx, Bx, Vx):

- compute mean of each metric over R runs
- compute standard deviation
- report min/max where useful

Rationale:

Reduce noise and support statistically meaningful comparisons.

---

## Hypothesis Testing Strategy

### H1 (Latency Effects)

Method:

- plot latency vs block time variance
- plot latency vs inclusion delay
- check stall occurrence

Expected pattern:

Monotonic degradation before stalls.

---

### H2 (Bandwidth Effects)

Method:

- plot bandwidth vs inclusion delay
- inspect irregular block times
- correlate with peer connectivity

---

### H3 (Validator Availability)

Method:

- compare V0 vs V1 vs V2
- observe stall_event_count
- verify quorum threshold behavior

Decision rule:

Consensus considered broken if stall_event_count > 0.

---

### H4 (Combined Stress)

Method:

- compare single-factor vs combined scenarios
- detect non-linear degradation
- analyze recovery behavior

---

### H5 (Robustness Boundary)

Method:

- map parameter space
- mark configurations with stalls
- identify transition region

Visualization:

Heatmap or phase diagram recommended.

---

## Visualization Plan

Recommended plots:

1. Latency vs block time variance (line plot)
2. Latency vs inclusion delay (line plot)
3. Bandwidth vs inclusion delay (line plot)
4. Validator failures vs stall probability (bar plot)
5. Robustness phase diagram (heatmap)

All plots should include:

- mean value
- error bars (std dev)
- number of runs (R)

---

## Statistical Treatment

Given the experimental nature:

- descriptive statistics are primary
- confidence intervals optional
- hypothesis tests optional (not required for master level)

Focus:

Clear trends and reproducible behavior.

---

## Result Validation

Before interpreting results:

- verify peer connectivity during runs
- check for measurement errors
- confirm load generator activity
- inspect logs for anomalies