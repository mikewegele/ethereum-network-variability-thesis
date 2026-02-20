# Reproducibility

## Environment Control

Experiments are executed in a containerized environment using Docker to ensure consistent software versions and configurations.

---

## Version Pinning

The following components are fixed per run:

- Besu Docker image tag
- genesis configuration
- number of validators
- block period configuration

The git commit hash of the repository is stored in meta.json.

---

## Deterministic Run Procedure

Each experiment run follows the standardized run procedure defined in docs/run-procedure.md.

All parameter configurations are explicitly recorded.

---

## Artifact Preservation

For each run, the following artifacts are stored:

- raw RPC measurements
- client logs
- run metadata
- derived metrics

This enables full offline re-analysis.

---

## Randomness Control

Transaction generation uses deterministic rate control.

Future work may include seeded randomness for burst workloads.