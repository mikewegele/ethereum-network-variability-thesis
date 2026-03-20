# Open Questions and Risks

This document tracks open technical and methodological questions that may affect the experimental study.

---

## Client Behavior

- Does Besu IBFT2 strictly follow expected quorum behavior under validator failures?
- Are there implementation-specific timeouts that affect liveness under high latency?
- How sensitive is IBFT2 to asymmetric latency?

Priority: HIGH

---

## Network Emulation

- How accurately does tc/netem emulate real-world latency and bandwidth?
- Are impairments applied symmetrically between all validators?
- Does Docker networking introduce additional latency?

Priority: HIGH

---

## Measurement Accuracy

- Is JSON-RPC polling frequency sufficient to detect short stalls?
- How large is clock skew between containers?
- Does polling introduce measurable overhead?

Priority: MEDIUM

---

## Load Generation

- Is the chosen transaction rate sufficient to keep the system busy?
- Does the load generator become a bottleneck?
- Should multiple sender accounts be used?

Priority: MEDIUM

---

## Stall Detection Robustness

- Is the stall threshold (currently 10s) appropriate across all scenarios?
- How to distinguish temporary delay vs true liveness failure?
- Should peer connectivity be part of the stall definition?

Priority: HIGH

---

## Experiment Coverage

- Are the selected parameter levels sufficient to expose the robustness boundary?
- Should additional latency levels be added adaptively?
- How many repetitions are needed for stable statistics?

Priority: MEDIUM

---

## External Validity

- How representative is a 4-validator network?
- How do results scale with more validators?
- How different would public Ethereum behavior be?

Priority: LOW (discussion section)

---

## Tooling Risks

- Docker resource limits on the host machine
- Log volume size for long experiment batches
- Potential RPC timeouts under heavy stress

Priority: MEDIUM

---

## Next Investigation Steps

To be updated during implementation and early experiments.