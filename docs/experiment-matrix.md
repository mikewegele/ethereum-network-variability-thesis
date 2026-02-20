# Experiment Matrix

This document defines the concrete experiment configurations.

## Parameter Levels

Latency:
- L0: 0 ms
- L1: 50 ms
- L2: 100 ms
- L3: 200 ms
- L4: 400 ms

Bandwidth:
- B0: unlimited
- B1: 10 Mbps
- B2: 1 Mbps
- B3: 128 kbps

Validator availability:
- V0: 0 offline
- V1: 1 offline
- V2: 2 offline

---

## Phase 1: Single-Factor Experiments

Only one stress factor varied at a time.

Examples:

- (L1, B0, V0)
- (L2, B0, V0)
- (L3, B0, V0)
- (L4, B0, V0)

- (L0, B1, V0)
- (L0, B2, V0)
- (L0, B3, V0)

- (L0, B0, V1)
- (L0, B0, V2)

Purpose:
Identify primary sensitivity of the system.

---

## Phase 2: Combined Stress

Selected combinations of high-stress scenarios.

Examples:

- (L2, B2, V0)
- (L3, B2, V1)
- (L4, B3, V1)
- (L4, B3, V2)

Purpose:
Identify robustness boundaries and failure regions.

---

## Repetitions

Each experiment configuration is repeated:

- R = 5 runs

Purpose:
Reduce variance and increase statistical confidence.