import argparse
import json
import os
import time
import urllib.request


def rpc_call(url: str, method: str, params):
    payload = json.dumps(
        {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    ).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        if "error" in data:
            raise RuntimeError(str(data["error"]))
        return data["result"]


def hex_to_int(x: str) -> int:
    return int(x, 16)


def ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)


def write_jsonl(path: str, obj: dict):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def write_json(path: str, obj: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def robust_read_block_number(rpc_url: str, budget_s: float, sleep_s: float = 0.5):
    deadline = time.time() + max(0.1, budget_s)
    last_err = None
    while time.time() < deadline:
        try:
            bn_hex = rpc_call(rpc_url, "eth_blockNumber", [])
            return hex_to_int(bn_hex), None
        except Exception as e:
            last_err = str(e)
            time.sleep(sleep_s)
    return None, last_err


def fetch_blocks(rpc_url: str, out_path: str, start_bn: int, end_bn: int):
    for h in range(start_bn, end_bn + 1):
        try:
            block = rpc_call(rpc_url, "eth_getBlockByNumber", [hex(h), False])
            write_jsonl(out_path, {
                "blockNumber": h,
                "blockTimestamp": hex_to_int(block["timestamp"]),
                "txCount": len(block.get("transactions", []))
            })
        except Exception as e:
            write_jsonl(out_path, {"blockNumber": h, "error": str(e)})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rpc", default="http://localhost:8545")
    ap.add_argument("--out", required=True)
    ap.add_argument("--duration", type=int, required=True)
    ap.add_argument("--blocks_hz", type=float, default=1.0)
    ap.add_argument("--peers_hz", type=float, default=0.5)
    ap.add_argument("--validators_hz", type=float, default=0.1)
    ap.add_argument("--end_read_budget_s", type=float, default=20.0)
    ap.add_argument("--fetch_blocks_after", action="store_true", default=True)
    args = ap.parse_args()

    rpc_dir = os.path.join(args.out, "rpc")
    ensure_dir(rpc_dir)

    blocks_path = os.path.join(rpc_dir, "blocks.jsonl")
    head_path = os.path.join(rpc_dir, "head.jsonl")
    peers_path = os.path.join(rpc_dir, "peers.jsonl")
    validators_path = os.path.join(rpc_dir, "validators.jsonl")
    meta_path = os.path.join(rpc_dir, "run_meta.json")

    t0 = time.time()
    next_blocks = t0
    next_peers = t0
    next_validators = t0

    start_bn = None
    end_bn = None

    while True:
        now = time.time()
        if now - t0 >= args.duration:
            break

        if now >= next_blocks:
            try:
                bn_hex = rpc_call(args.rpc, "eth_blockNumber", [])
                bn = hex_to_int(bn_hex)
                if start_bn is None:
                    start_bn = bn
                end_bn = bn
                write_jsonl(head_path, {"ts_local": now, "blockNumber": bn})
            except Exception as e:
                write_jsonl(head_path, {"ts_local": now, "error": str(e)})
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

    t1 = time.time()

    end_bn_final, end_err = robust_read_block_number(args.rpc, args.end_read_budget_s)
    if end_bn_final is not None:
        end_bn = end_bn_final
        write_jsonl(head_path, {"ts_local": time.time(), "blockNumber_final": end_bn})
    else:
        write_jsonl(head_path, {"ts_local": time.time(), "end_blockNumber_error": end_err})

    meta = {
        "ts_start_local": t0,
        "ts_end_local": t1,
        "duration_s_target": args.duration,
        "duration_s_observed": t1 - t0,
        "start_blockNumber": start_bn,
        "end_blockNumber": end_bn,
        "rpc": args.rpc,
        "fetch_blocks_after": bool(args.fetch_blocks_after),
        "end_read_budget_s": args.end_read_budget_s
    }
    write_json(meta_path, meta)

    if args.fetch_blocks_after and start_bn is not None and end_bn is not None and end_bn >= start_bn:
        fetch_t0 = time.time()
        if os.path.exists(blocks_path):
            os.remove(blocks_path)
        fetch_blocks(args.rpc, blocks_path, start_bn, end_bn)
        fetch_t1 = time.time()

        meta2 = dict(meta)
        meta2.update({
            "fetch_started_local": fetch_t0,
            "fetch_finished_local": fetch_t1,
            "fetch_duration_s": fetch_t1 - fetch_t0,
            "fetched_blocks_expected": (end_bn - start_bn + 1)
        })
        write_json(meta_path, meta2)


if __name__ == "__main__":
    main()