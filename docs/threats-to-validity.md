# Threats to Validity

## Internal Validity

Potential risks:

- measurement overhead from RPC polling
- clock skew between containers
- misclassification of stalls due to transient delays

Mitigation:

- low-frequency polling
- stall threshold with safety margin
- repeated experiment runs

---

## External Validity

Limitations:

- private Ethereum network with limited validators
- controlled laboratory environment
- synthetic network impairments

Implication:

Results may not directly transfer to public blockchain deployments.

---

## Construct Validity

Risks:

- block time variance may not capture all instability aspects
- inclusion delay depends on workload characteristics

Mitigation:

- multiple complementary metrics
- qualitative log inspection