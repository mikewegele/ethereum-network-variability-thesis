# Metrics Definition

This document defines the quantitative metrics used to evaluate performance degradation and consensus stability.

---

## Block Time

### Definition

Block time is defined as the time difference between two consecutive blocks:

block_time_i = timestamp(block_i) - timestamp(block_{i-1})

### Derived Metric

Block time variance is used as an indicator of instability.

### Purpose

- Detect early performance degradation
- Identify irregular block production
- Support detection of unstable consensus behavior

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

## Stalled Consensus Detection

### Definition

Consensus is considered stalled if no new block is produced within:

stall_threshold = 3 × expected_block_time

Given the configured block period of 2 seconds:

stall_threshold = 6 seconds

### Detection Rule

Stall condition holds if:

- no new block is observed within the threshold, and
- pending transactions exist.

### Purpose

- Detect liveness failures
- Identify robustness boundaries
- Distinguish slowdown from true consensus failure

---

## Peer Connectivity (Supporting Metric)

### Definition

Number of connected peers reported by the client.

### Purpose

- Validate network partition scenarios
- Support interpretation of failures