# Expected Results

This document outlines the expected qualitative behavior of the system under different network stress conditions. The purpose is to guide later interpretation and detect unexpected behavior.

Consensus progress is evaluated using:

- block time statistics
- chain growth rate (CGR)
- stall detection based on:

  T_stall = k × T_baseline  
  with k ∈ {3, 4, 5, 6}

---

## Baseline Behavior (No Stress)

### Expected

- stable block production near configured block period (~2 seconds)
- low block time variance
- high and stable chain growth rate
- no stall events for any tested k
- stable peer connectivity

### Interpretation

This establishes the reference operating point and defines T_baseline used for stall detection.

CGR should remain constant and close to:

1 / block_period

---

## Increasing Latency

### Expected Trend

As latency increases:

1. block time variance increases gradually
2. transaction inclusion delay increases
3. chain growth rate decreases moderately
4. stall events appear only at high latency levels
5. stall occurrence should be consistent across k values at high stress

### Expected Shape

- smooth degradation phase
- followed by sharp transition region
- then sustained stall region (CGR approaching zero)

### Warning Signs

Unexpected if:

- stalls occur at very low latency
- stall classification depends heavily on k
- CGR collapses abruptly at moderate latency
- peer connectivity drops without injected faults

---

## Bandwidth Limitation

### Expected Trend

Under decreasing bandwidth:

- minor impact at moderate limits (≥10 Mbps)
- gradual increase in inclusion delay
- increased block time variance under severe limits
- chain growth rate decreases only at extreme bandwidth constraints
- stalls occur only when communication becomes heavily constrained

### Expected Sensitivity

Bandwidth effects are expected to be weaker than latency effects until near saturation.

Stall events should appear only when CGR significantly decreases.

---

## Validator Availability

### Expected Behavior (N = 4)

- V0 (0 offline): fully stable
- V1 (1 offline): consensus remains live
- V2 (2 offline): consensus stalls due to quorum violation

### Expected Metrics

- For V2:
    - CGR approaches zero
    - repeated stall events across all k values
    - sustained inter-block gaps

### Key Check

This validates correct IBFT quorum behavior and confirms that stall detection aligns with theoretical quorum requirements.

---

## Combined Stress Scenarios

### Expected Trend

Combined impairments should:

- amplify block time variance
- reduce chain growth rate faster
- trigger stalls earlier than single-factor stress

### Expected Pattern

Non-linear degradation is likely.

Transition region should be sharper compared to single-factor experiments.

---

## Robustness Boundary

### Expected Observation

There exists a parameter region where the system transitions from:

stable → degraded → stalled

This transition should be observable through:

- sharp drop in chain growth rate
- repeated stall events
- significant increase in maximum inter-block gap

### Robustness Criterion

The boundary should remain qualitatively stable across:

- k ∈ {3, 4, 5, 6}
- repeated experimental runs

This stability confirms that the observed transition is a system property rather than an artifact of parameter selection.

---

## Recovery Behavior

### Expected

After removing impairments:

- block production resumes
- chain growth rate returns to baseline levels
- peer connectivity stabilizes
- inclusion delay normalizes

### Important Note

Failure to recover may indicate:

- persistent partition effects
- implementation limitations
- misconfiguration
- timeout escalation effects in IBFT

---

## Unexpected Outcomes (Investigation Required)

The following observations require deeper analysis:

- stalls under light stress
- strong dependence on k value
- no stalls even after quorum violation
- highly irregular block production at baseline
- persistent peer disconnections
- inconsistent behavior across repetitions

Such cases must be cross-checked with logs, network conditions, and timeout parameters.