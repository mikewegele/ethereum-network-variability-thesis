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
- compute chain growth rate (CGR)
- detect stall events (k-based)
- store summary in structured results file

Output:

experiments/results/<run_id>/summary.json

---

## Derived Metrics

### Block Time Statistics

From blocks.jsonl:

- mean block time
- variance
- maximum inter-block gap

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

### Chain Growth Indicators

From block observations:

- CGR(W) with W = 60s
- trend of CGR across stress levels

Purpose:

Quantify consensus progress rate continuously.

---

### Stall Indicators

Using:

T_stall = k × T_baseline

Metrics:

- stall_event_count
- max_interblock_gap
- time_to_first_stall

Sensitivity:

Evaluate k ∈ {3,4,5,6}

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
- plot latency vs CGR
- check stall occurrence across k values

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

Consensus considered broken if stall occurs consistently across k values.

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
- mark configurations with sustained stalls
- identify transition region stable across k values

Visualization:

Heatmap or phase diagram recommended.

---

## Statistical Treatment

Given the experimental nature:

- descriptive statistics are primary
- confidence intervals optional
- hypothesis tests optional

Focus:

Clear trends, reproducibility, and stability across parameter sensitivity.