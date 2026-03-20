# Transaction Load Design

## Objective

Background transactions are generated to ensure the network is continuously processing work during experiments. This enables reliable detection of performance degradation and stalled consensus.

---

## Load Model

A constant-rate transaction generator is used.

Initial configuration:

- tx_rate: 2 transactions per second
- tx_size: simple ETH transfer
- sender accounts: pre-funded accounts from genesis
- submission mode: sequential, non-burst

Rationale:
A steady low background load avoids saturating the system while ensuring meaningful inclusion delay measurements.

---

## Recorded Data

For each submitted transaction:

- local_submission_timestamp
- tx_hash
- target_node (RPC endpoint)

Stored in:

rpc/tx.jsonl

---

## Inclusion Tracking

For each transaction:

- poll for transaction receipt
- record inclusion block number
- record inclusion timestamp

Derived metric:

tx_inclusion_delay =
block_timestamp(inclusion_block)
− local_submission_timestamp

---

## Load During Phases

- Warm-up: no load
- Baseline: low load active
- Measurement: load active
- Recovery: load active

---

## Future Extensions

- burst load scenarios
- higher throughput stress
- multi-sender workloads