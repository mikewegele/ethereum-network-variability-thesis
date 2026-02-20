# Research Hypotheses

This section defines the testable hypotheses regarding the impact of network variability on private Ethereum networks using IBFT2.

---

## H1 — Latency-Induced Performance Degradation

**Hypothesis**

Increasing network latency leads to increased block time variance and transaction inclusion delay while consensus remains operational within the synchrony bounds.

**Rationale**

IBFT2 relies on timely message exchange. Higher latency increases communication delays, which should manifest as performance degradation before liveness is affected.

**Test Metrics**

- block time variance
- transaction inclusion delay
- stall event count

**Expected Outcome**

Gradual degradation without stalls for moderate latency levels.

---

## H2 — Bandwidth Constraint Sensitivity

**Hypothesis**

Severe bandwidth limitations increase transaction inclusion delay and may lead to irregular block production due to delayed message propagation.

**Rationale**

IBFT requires multiple message exchanges per round. Bandwidth constraints can delay quorum formation.

**Test Metrics**

- transaction inclusion delay
- block time variance
- peer connectivity (supporting)

**Expected Outcome**

Limited impact at moderate bandwidth limits, stronger degradation at extreme constraints.

---

## H3 — Quorum Violation Causes Liveness Failure

**Hypothesis**

If the number of available validators falls below the IBFT quorum requirement, consensus progress stalls.

**Rationale**

IBFT guarantees safety under partial synchrony but requires quorum participation for liveness.

**Test Metrics**

- stall event detection
- block production continuity
- peer count

**Expected Outcome**

Stable operation with ≤1 validator offline (N=4), stalled consensus with ≥2 offline.

---

## H4 — Combined Stress Amplifies Instability

**Hypothesis**

Combined network impairments (latency + bandwidth + reduced validator availability) trigger consensus instability earlier than single-factor stress.

**Rationale**

Multiple impairments jointly increase the probability of delayed or failed quorum formation.

**Test Metrics**

- block time variance
- stall event count
- recovery behavior

**Expected Outcome**

Non-linear degradation and earlier onset of stalled consensus.

---

## H5 — Existence of a Robustness Boundary

**Hypothesis**

There exists a threshold region in the network parameter space at which the system transitions from degraded but correct operation to stalled consensus.

**Rationale**

Partially synchronous consensus protocols exhibit phase-transition-like behavior under adverse timing conditions.

**Test Metrics**

- stall occurrence probability
- block time variance trends
- recovery success

**Expected Outcome**

Observable boundary between stable and unstable operating regions.