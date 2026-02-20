# Expected Results

This document outlines the expected qualitative behavior of the system under different network stress conditions. The purpose is to guide later interpretation and detect unexpected behavior.

---

## Baseline Behavior (No Stress)

### Expected

- stable block production at configured block period (~2 seconds)
- low block time variance
- low and stable transaction inclusion delay
- no stall events
- stable peer connectivity

### Interpretation

This establishes the reference operating point for all subsequent comparisons.

---

## Increasing Latency

### Expected Trend

As latency increases:

1. block time variance increases gradually
2. transaction inclusion delay increases
3. consensus remains operational under moderate latency
4. stalls may appear only at high latency levels

### Expected Shape

- monotonic or near-monotonic degradation
- smooth curve before any failure region

### Warning Signs

Unexpected if:

- stalls occur at very low latency
- block production becomes irregular early
- peer connectivity drops without injected faults

---

## Bandwidth Limitation

### Expected Trend

Under decreasing bandwidth:

- minor impact at moderate limits (≥10 Mbps)
- increasing inclusion delay at low bandwidth
- possible irregular block times under severe limits
- stalls only under extreme bandwidth constraints

### Expected Sensitivity

Bandwidth effects are expected to be weaker than latency effects until the network becomes heavily constrained.

---

## Validator Availability

### Expected Behavior (N = 4)

- V0 (0 offline): fully stable
- V1 (1 offline): consensus should remain live
- V2 (2 offline): consensus should stall (quorum violation)

### Key Check

This experiment validates correct IBFT quorum behavior.

---

## Combined Stress Scenarios

### Expected Trend

Combined impairments should:

- amplify performance degradation
- increase block time variance faster
- trigger stalls earlier than single-factor stress

### Expected Pattern

Non-linear degradation is likely.

---

## Robustness Boundary

### Expected Observation

There exists a parameter region where the system transitions from:

stable → degraded → stalled

### Expected Visualization

In the parameter space:

- clear region of stable operation
- transition zone with increasing instability
- failure region with frequent stalls

This boundary is a primary contribution of the thesis.

---

## Recovery Behavior

### Expected

After removing impairments:

- block production should resume
- peer connectivity should recover
- inclusion delay should normalize

### Important Note

Failure to recover may indicate:

- persistent partition effects
- implementation limitations
- misconfiguration

---

## Unexpected Outcomes (Investigation Required)

The following observations require deeper analysis:

- stalls under light stress
- no stalls even after quorum violation
- highly irregular block production at baseline
- persistent peer disconnections
- inconsistent behavior across repetitions

Such cases must be cross-checked with logs and network conditions.