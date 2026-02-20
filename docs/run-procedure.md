# Experimental Run Procedure

Each experiment run follows the same procedure.

## Step 1 — Network Initialization

- Start all validators
- Wait for network stabilization
- Verify peer connectivity

Warm-up time:
60 seconds

---

## Step 2 — Baseline Observation

- Observe block production
- Record baseline metrics

Duration:
60 seconds

---

## Step 3 — Apply Network Stress

- Apply configured impairment
- Start background transaction load

---

## Step 4 — Measurement Phase

- Record all metrics
- Monitor consensus behavior

Duration:
180 seconds

---

## Step 5 — Recovery Phase

- Remove impairment
- Observe recovery behavior

Duration:
60 seconds

---

## Step 6 — Shutdown and Persist Logs

- Stop network
- Store logs and metadata