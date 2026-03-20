# Run Artifacts & Naming

## Run ID Format

YYYYMMDD-HHMM_<Lx>_<Bx>_<Vx>_R<k>

Example:
20260220-2031_L3_B2_V1_R4

## Required Metadata Fields (meta.json)

- run_id
- git_commit
- besu_image
- chain_id
- block_period_seconds
- factors:
    - latency_ms
    - bandwidth_kbps (or "unlimited")
    - validators_offline
- timings:
    - warmup_s
    - baseline_s
    - measure_s
    - recovery_s
- notes (free text)

## Minimal Acceptance Criteria

A run is valid if:
- JSON-RPC responded throughout measurement phase
- at least one block was observed (or stall was detected explicitly)
- logs are complete for all validators