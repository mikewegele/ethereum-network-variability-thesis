# PoA Ethereum Network Variability

Experimental framework for evaluating IBFT-based private Ethereum networks under network stress.

## Quickstart (macOS)

1. Install Docker Desktop
2. Copy `.env.example` to `.env`
3. Generate genesis + keys:
   docker run --rm -v ${PWD}:/data hyperledger/besu:latest \
   operator generate-blockchain-config \
   --config-file=/data/config/ibftConfigFile.json \
   --to=/data/nodes/networkFiles \
   --private-key-file-name=key
4. Copy generated genesis to `config/genesis.json`
5. Copy validator keys into `nodes/validatorX/data`
6. Start first node:
   docker compose up -d validator1
7. Extract enode from logs and put into `.env`
8. Start full network:
   docker compose up -d