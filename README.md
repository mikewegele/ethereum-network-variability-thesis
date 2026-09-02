# Impact of Network Variability on Private Ethereum Networks

Experimental framework and analysis code for evaluating the performance and consensus stability of private Ethereum networks under controlled network impairments.

This repository accompanies the Master's thesis:

> **Impact of Network Variability on Performance and Consensus Stability in Private Ethereum Networks**

The experiments use **Hyperledger Besu** with **QBFT consensus** and investigate how latency, packet loss, bandwidth limitations, and network partitions affect block production, chain growth, stall behavior, and consensus stability.

---

## Overview

Private Ethereum networks are often deployed in environments in which network conditions cannot be assumed to remain stable. Increased latency, packet loss, bandwidth limitations, or temporary partitions can delay consensus communication and eventually affect liveness.

This project provides a reproducible experimental environment for studying these effects under controlled conditions.

The framework combines:

- a containerized Hyperledger Besu network,
- deterministic network impairments using Linux traffic control,
- automated transaction generation,
- RPC-based metric collection,
- repeated experiment execution,
- phase-based performance analysis,
- and scripts for generating the figures and result tables used in the thesis.

The main objective is not only to measure performance degradation, but also to identify the transition from normal operation to degraded behavior and eventual consensus stalls.

---

## Experimental Setup

The evaluated network consists of:

| Component | Configuration |
|---|---|
| Consensus protocol | QBFT |
| Validators | 4 |
| Fault tolerance | 1 Byzantine validator |
| RPC node | 1 |
| Block period | 2 s |
| Request timeout | 4 s |
| Transaction rate | 5 tx/s |
| Maximum in-flight transactions | 32 |

Each experiment is divided into four phases:

| Phase | Duration | Purpose |
|---|---:|---|
| Warm-up | 60 s | Allow the network and workload to stabilize |
| Baseline | 60 s | Measure behavior without impairment |
| Stress | 180 s | Apply the selected network impairment |
| Recovery | 60 s | Remove the impairment and observe recovery |

This phase structure makes it possible to compare network behavior before, during, and after an impairment within the same run.

---

## Network Impairments

Four classes of network variability are evaluated.

### Latency

Additional communication delay is introduced between validators to study how increasing message propagation times affect QBFT block production and liveness.

### Packet Loss

Artificial packet loss is applied to validator communication to investigate the point at which repeated message loss prevents reliable consensus progress.

### Bandwidth Limitation

Validator bandwidth is progressively restricted to determine how limited network capacity affects block production and consensus communication.

### Network Partitions

Validators are separated into different network partitions to evaluate the relationship between connectivity, quorum availability, and consensus liveness.

The network conditions are applied using `tc`/`netem` and the scripts in:

```text
scripts/net/
```

---

## Metrics

The analysis focuses on metrics that capture both performance degradation and loss of liveness.

### Inter-Block Time

Time between consecutive finalized blocks.

It provides a direct measure of how quickly the network continues producing blocks under stress.

### Chain Growth Rate

Number of finalized blocks produced per second over a defined observation window.

This metric captures sustained blockchain progress and complements individual inter-block times.

### Stall Duration

Duration of periods in which block finalization is interrupted beyond the configured stall threshold.

### Missing Finalization Intervals

Number of expected finalization intervals without successful block production.

### Stability Regime

Each run is classified into one of three operational regimes:

- **Stable** — normal block production without relevant stalls
- **Degraded** — consensus remains live, but performance or regularity deteriorates
- **Stalled** — sustained loss of consensus progress

The classification combines chain growth, missing finalization intervals, and stall duration rather than relying on a single metric.

---

## Repository Structure

```text
.
├── config/
│   └── genesis.json
│
├── docker-compose.yml
├── qbftConfigFile.json
├── requirements.txt
│
├── docs/
│   └── method.md
│
├── experiments/
│   ├── analysis/
│   │   ├── qbft_logs/
│   │   └── results_export/
│   │
│   └── exports/
│       ├── dataset/
│       ├── final_series/
│       └── jitter_series/
│
└── scripts/
    ├── analysis/
    ├── collect/
    ├── load/
    ├── net/
    ├── orchestration/
    └── utils/
```

### `scripts/orchestration`

Controls complete experiment series and coordinates workload generation, metric collection, and network impairment.

### `scripts/net`

Applies and removes latency, packet loss, bandwidth restrictions, node isolation, and network partitions.

### `scripts/load`

Generates accounts and transaction workload.

### `scripts/collect`

Collects blockchain and RPC information during experiment execution.

### `scripts/analysis`

Processes experiment results, computes metrics, classifies stability regimes, and generates thesis figures.

### `experiments/exports`

Contains compact processed result tables from the final experiment series.

### `experiments/analysis/qbft_logs`

Contains processed QBFT log information used for the protocol-level analysis of later-round block imports.

---

## Installation

### Requirements

The experiments were developed for a Docker-based local environment.

Required software:

- Docker
- Docker Compose
- Python 3
- Linux traffic-control support inside the network environment
- Hyperledger Besu Docker image

Install the Python dependencies with:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Network Configuration

The repository contains the QBFT configuration used to generate the validator network:

```text
qbftConfigFile.json
```

and the resulting genesis configuration:

```text
config/genesis.json
```

Validator private keys and runtime blockchain databases are intentionally **not included in the repository**.

They should be generated locally before running a new network.

A QBFT configuration can be generated using the Hyperledger Besu operator tooling, for example:

```bash
docker run --rm \
  -v "${PWD}:/data" \
  hyperledger/besu:latest \
  operator generate-blockchain-config \
  --config-file=/data/qbftConfigFile.json \
  --to=/data/qbftOutput \
  --private-key-file-name=key
```

The generated validator keys can then be placed in the corresponding local validator directories used by `docker-compose.yml`.

Generated keys, account files, node databases, and environment files are excluded through `.gitignore`.

---

## Running the Network

After the validator configuration has been generated, start the network with:

```bash
docker compose up -d
```

Check the running containers with:

```bash
docker compose ps
```

and stop the network with:

```bash
docker compose down
```

---

## Running Experiments

Experiment orchestration is located in:

```text
scripts/orchestration/
```

The final experiment series can be started with:

```bash
bash scripts/orchestration/run_all_final_series.sh
```

Individual network impairments are implemented separately under:

```text
scripts/net/
```

This separation allows the same experiment structure to be reused for latency, packet loss, bandwidth, and partition experiments.

---

## Result Analysis

The main analysis implementation is:

```text
scripts/analysis/analyze_run.py
```

It derives the performance and liveness metrics from the collected block and run metadata.

Processed experiment results are available under:

```text
experiments/exports/final_series/
```

including:

```text
bandwidth_stress_summary.csv
latency_stress_summary.csv
packetloss_stress_summary.csv
summary.csv
```

Additional latency and QBFT protocol analysis data are stored under:

```text
experiments/analysis/
```

---

## Figure Generation

The repository includes the scripts used to create the result figures presented in the thesis.

Important scripts include:

```text
scripts/analysis/plot_result_figures.py
scripts/analysis/plot_latency_jitter.py
scripts/analysis/plot_later_round_imports.py
```

For example, the later-round QBFT import analysis can be generated with:

```bash
python scripts/analysis/plot_later_round_imports.py
```

The script uses the processed protocol data in:

```text
experiments/analysis/qbft_logs/
```

and generates the corresponding figure locally.

Generated plots are not version-controlled because they can be reproduced from the included scripts and processed datasets.

---

## Main Findings

The experiments show that the different network impairments lead to substantially different degradation patterns.

**Latency** produces a comparatively broad transition from stable to degraded and eventually stalled operation. Moderate additional delay can therefore affect block production before consensus liveness is completely lost.

**Packet loss** exhibits a much sharper transition. The network remains comparatively robust at lower loss levels, while sufficiently high loss rapidly causes repeated or complete stalls.

**Bandwidth limitations** primarily lead to gradual performance degradation. The network continues making progress under substantial bandwidth restrictions before very low available capacity strongly increases inter-block times.

**Network partitions** demonstrate the quorum dependency of QBFT directly. A `3 | 1` split retains a validator quorum and can continue producing blocks, whereas a `2 | 2` split prevents either partition from reaching the required quorum and therefore stalls consensus.

The results show that consensus failure should not be treated as a purely binary event. Performance degradation and increasing irregularity can become visible before complete loss of liveness.

---

## Data Availability

The repository intentionally contains **processed experiment results rather than the complete raw experiment archive**.

Included data covers the result tables and processed protocol information required for the analyses and figures contained in the thesis.

Large raw experiment directories, validator logs, generated plots, blockchain databases, and temporary experiment artifacts are excluded from version control.

This keeps the repository compact while preserving the code, configuration, methodology, and processed data required to understand and reproduce the analysis.

---

## Security Notice

The repository does not contain operational validator private keys or load-test account credentials.

The following artifacts are intentionally excluded:

```text
.env
nodes/
qbftOutput/keys/
experiments/load_accounts.json
```

Keys generated for local experiments should be treated as disposable test credentials and must not be reused for production systems or accounts containing real assets.

---

## Reproducibility

The repository is intended to provide the complete experimental logic required to reproduce the study:

1. generate a local four-validator QBFT network,
2. start the Docker environment,
3. execute the workload,
4. apply controlled network impairments,
5. collect RPC and protocol information,
6. calculate performance and liveness metrics,
7. classify experiment runs by stability regime,
8. regenerate the result figures.

Exact experiment parameters and methodological details are described in:

```text
docs/method.md
```

---

## Thesis

This repository accompanies the Master's thesis:

**Impact of Network Variability on Performance and Consensus Stability in Private Ethereum Networks**

The study investigates how controlled network variability affects the performance and consensus stability of private Ethereum networks using Hyperledger Besu and QBFT.

---

## Author

**Mike Wegele**

Freie Universität Berlin  
Master's Program in Computer Science