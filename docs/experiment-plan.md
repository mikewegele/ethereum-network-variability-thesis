# Experimental Plan

## Objective

The objective of this study is to evaluate the impact of network variability on the performance and consensus stability of private Ethereum networks using IBFT2.

The experiments aim to identify robustness boundaries at which the system transitions from degraded but correct operation to stalled consensus.

---

## Experimental Factors

### Network Latency

Latency is applied symmetrically between validator nodes.

Test levels:

- L0: 0 ms (baseline)
- L1: 50 ms
- L2: 100 ms
- L3: 200 ms
- L4: 400 ms

Rationale:
These levels cover typical data center conditions up to severely degraded wide-area scenarios.

---

### Bandwidth Limitation

Bandwidth limits are applied on inter-validator communication.

Test levels:

- B0: unlimited (baseline)
- B1: 10 Mbps
- B2: 1 Mbps
- B3: 128 kbps

Rationale:
These levels emulate constrained edge and degraded network environments.

---

### Validator Availability

Temporary validator outages are introduced.

Test levels (for N=4 validators):

- V0: 0 validators offline
- V1: 1 validator offline
- V2: 2 validators offline

Rationale:
IBFT requires quorum participation; these scenarios explore behavior near and beyond quorum limits.

---

## Experimental Procedure

For each parameter configuration:

1. Start the network and allow warm-up.
2. Apply network impairment.
3. Submit background transactions.
4. Record metrics.
5. Detect degraded or stalled consensus behavior.
6. Repeat each experiment multiple times.

---

## Expected Outcomes

- Increasing latency and bandwidth constraints will increase block time variance.
- Severe network stress or insufficient validator availability will lead to stalled consensus.
- Clear robustness thresholds can be identified.