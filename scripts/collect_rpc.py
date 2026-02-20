import argparse
import json
import os
import time
import urllib.request

def rpc_call(url: str, method: str, params):
    payload = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))["result"]

def hex_to_int(x: str) -> int:
    return int(x, 16)

def ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)

def write_jsonl(path: str, obj: dict):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rpc", default="http://localhost:8545")
    ap.add_argument("--out", required=True)
    ap.add_argument("--duration", type=int, required=True)
    ap.add_argument("--blocks_hz", type=float, default=1.0)
    ap.add_argument("--peers_hz", type=float, default=0.5)
    ap.add_argument("--validators_hz", type=float, default=0.1)
    args = ap.parse_args()

    rpc_dir = os.path.join(args.out, "rpc")
    ensure_dir(rpc_dir)

    blocks_path = os.path.join(rpc_dir, "blocks.jsonl")
    peers_path = os.path.join(rpc_dir, "peers.jsonl")
    validators_path = os.path.join(rpc_dir, "validators.jsonl")

    t0 = time.time()
    next_blocks = t0
    next_peers = t0
    next_validators = t0

    last_block_num = None

    while True:
        now = time.time()
        if now - t0 >= args.duration:
            break

        if now >= next_blocks:
            try:
                bn_hex = rpc_call(args.rpc, "eth_blockNumber", [])
                bn = hex_to_int(bn_hex)
                if last_block_num is None or bn != last_block_num:
                    block = rpc_call(args.rpc, "eth_getBlockByNumber", [bn_hex, False])
                    write_jsonl(blocks_path, {
                        "ts_local": now,
                        "blockNumber": bn,
                        "blockTimestamp": hex_to_int(block["timestamp"]),
                        "txCount": len(block.get("transactions", []))
                    })
                    last_block_num = bn
            except Exception as e:
                write_jsonl(blocks_path, {"ts_local": now, "error": str(e)})

            next_blocks = now + (1.0 / max(args.blocks_hz, 0.01))

        if now >= next_peers:
            try:
                pc_hex = rpc_call(args.rpc, "net_peerCount", [])
                write_jsonl(peers_path, {"ts_local": now, "peerCount": hex_to_int(pc_hex)})
            except Exception as e:
                write_jsonl(peers_path, {"ts_local": now, "error": str(e)})

            next_peers = now + (1.0 / max(args.peers_hz, 0.01))

        if now >= next_validators:
            try:
                vals = rpc_call(args.rpc, "ibft_getValidatorsByBlockNumber", ["latest"])
                write_jsonl(validators_path, {"ts_local": now, "validators": vals})
            except Exception as e:
                write_jsonl(validators_path, {"ts_local": now, "error": str(e)})

            next_validators = now + (1.0 / max(args.validators_hz, 0.01))

        time.sleep(0.05)

if __name__ == "__main__":
    main()