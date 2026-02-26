# Research Hypotheses

This section defines the testable hypotheses regarding the impact of network variability on private Ethereum networks using IBFT2.

---

## H1 — Latency-Induced Performance Degradation

**Hypothesis**

Increasing network latency increases block time variance and transaction inclusion delay while consensus remains operational within synchrony bounds.

**Rationale**

IBFT2 relies on timely message exchange. Higher latency increases communication delay before liveness is affected.

**Test Metrics**

- block time variance
- transaction inclusion delay
- chain growth rate (CGR)
- stall event count

**Expected Outcome**

Gradual degradation without sustained stalls at moderate latency levels.

---

## H2 — Bandwidth Constraint Sensitivity

**Hypothesis**

Severe bandwidth limitations increase inclusion delay and may reduce chain growth rate due to delayed message propagation.

**Rationale**

IBFT requires multiple message exchanges per round. Bandwidth constraints slow quorum formation.

**Test Metrics**

- transaction inclusion delay
- block time variance
- CGR
- peer connectivity (supporting)

**Expected Outcome**

Limited impact at moderate bandwidth limits, stronger degradation at extreme constraints.

---

## H3 — Quorum Violation Causes Liveness Failure

**Hypothesis**

If available validators fall below the IBFT quorum requirement, consensus progress stalls.

**Rationale**

IBFT guarantees safety under partial synchrony but requires quorum participation for liveness.

**Test Metrics**

- stall event detection
- chain growth rate (approaching zero)
- block production continuity
- peer count

**Expected Outcome**

Stable operation with ≤1 validator offline (N=4), stalled consensus with ≥2 offline.

---

## H4 — Combined Stress Amplifies Instability

**Hypothesis**

Combined impairments (latency + bandwidth + reduced validator availability) trigger instability earlier than single-factor stress.

**Rationale**

Multiple impairments increase the probability of delayed quorum formation and timeout escalation.

**Test Metrics**

- block time variance
- stall event count
- CGR
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

- stall occurrence probability across k values
- chain growth rate trends
- recovery success

**Expected Outcome**

Observable boundary between stable and unstable operating regions, consistent across sensitivity parameters.