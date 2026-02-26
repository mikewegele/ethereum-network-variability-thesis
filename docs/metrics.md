# Metrics Definition

This document defines the quantitative metrics used to evaluate performance degradation and consensus stability.

---

## Block Time

### Definition

Block time is defined as the time difference between two consecutive blocks:

block_time_i = timestamp(block_i) - timestamp(block_{i-1})

### Derived Metrics

- mean block time
- block time variance
- maximum inter-block gap

### Purpose

- Detect early performance degradation
- Identify irregular block production
- Support detection of unstable consensus behavior

---

## Baseline Block Interval

### Definition

The baseline block interval is defined as the median inter-block time measured during a baseline run under stable network conditions:

T_baseline = median(block_time_baseline)

### Purpose

- Establish reference operating condition
- Derive non-arbitrary stall thresholds
- Enable consistent comparison across experiments

---

## Transaction Inclusion Delay

### Definition

Transaction inclusion delay is defined as:

tx_delay = timestamp(block_including_tx) - timestamp(tx_submission)

### Measurement Method

- Record local submission timestamp
- Extract inclusion block timestamp
- Compute delay per transaction

### Purpose

- Measure user-visible performance degradation
- Detect backlog formation under stress

---

## Chain Growth Rate (CGR)

### Definition

Chain growth rate over observation window W:

CGR(W) = number_of_blocks_in_window / W

Typical window size:

W = 60 seconds

### Purpose

- Quantify consensus progress rate
- Distinguish slowdown from near-stalled execution
- Provide continuous liveness indicator

---

## Stalled Consensus (Operational Definition)

### Definition

Consensus is operationally classified as stalled if:

block_time >= T_stall

where:

T_stall = k × T_baseline

and k is evaluated over a range:

k ∈ {3, 4, 5, 6}

### Rationale

- Avoid fixed time thresholds
- Scale detection relative to normal operation
- Ensure robustness against arbitrary parameter choice

### Sensitivity

Results are evaluated across multiple k values to verify that regime transitions are not artifacts of a single threshold.

### Purpose

- Detect liveness failures
- Identify robustness boundaries
- Distinguish gradual degradation from qualitative consensus breakdown

---

## Peer Connectivity (Supporting Metric)

### Definition

Number of connected peers reported by the client.

### Purpose

- Validate network partition scenarios
- Support interpretation of failures
- Correlate connectivity loss with stall events