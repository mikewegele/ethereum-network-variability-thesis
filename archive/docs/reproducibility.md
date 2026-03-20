# Reproducibility

## Environment Control

Experiments are executed in a containerized environment using Docker to ensure consistent software versions and configurations across runs.

---

## Version Pinning

The following components are fixed per run:

- Besu Docker image tag
- genesis configuration
- number of validators
- block period configuration
- IBFT2 timeout parameters

The git commit hash of the repository is stored in meta.json.

---

## Baseline Reference Run

A baseline run without network impairments (L0, B0, V0) is executed prior to stress experiments.

From this run, the median inter-block time is computed:

T_baseline = median(block_time_baseline)

This value serves as reference for stall detection.

---

## Operational Stall Threshold

Stall detection is derived from the baseline:

T_stall = k × T_baseline

where:

k ∈ {3, 4, 5, 6}

Multiple k values are evaluated to ensure that results are not artifacts of a single threshold choice.

---

## Deterministic Run Procedure

Each experiment run follows the standardized procedure defined in docs/run-procedure.md.

All parameter configurations and analysis parameters (k, window size) are explicitly recorded.

---

## Artifact Preservation

For each run, the following artifacts are stored:

- raw RPC measurements
- client logs
- run metadata
- derived metrics
- baseline reference values

This enables full offline re-analysis and verification of stall classification.

---

## Randomness Control

Transaction generation uses deterministic rate control.

Future work may include seeded randomness for burst workloads.