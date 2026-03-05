import argparse
import json
import os
import time
import urllib.request
from typing import Any, Dict, Optional, Tuple


def rpc_call(
    url: str,
    method: str,
    params: list,
    timeout_s: float = 10.0,
    retries: int = 3,
    sleep_s: float = 0.25,
) -> Any:
    last_err: Optional[Exception] = None
    for i in range(max(1, int(retries))):
        try:
            payload = json.dumps(
                {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
            ).encode("utf-8")
            req = urllib.request.Request(
                url, data=payload, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if "error" in data:
                    raise RuntimeError(str(data["error"]))
                if "result" not in data:
                    raise RuntimeError("RPC response missing 'result'")
                return data["result"]
        except Exception as e:
            last_err = e
            if i < max(1, int(retries)) - 1:
                time.sleep(sleep_s * (1.5 ** i))
    raise RuntimeError(str(last_err) if last_err is not None else "rpc_call failed")


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


def robust_read_block_number(
    rpc_url: str, budget_s: float, sleep_s: float = 0.5
) -> Tuple[Optional[int], Optional[str]]:
    deadline = time.monotonic() + max(0.1, float(budget_s))
    last_err: Optional[str] = None
    while time.monotonic() < deadline:
        try:
            bn_hex = rpc_call(rpc_url, "eth_blockNumber", [], retries=2, sleep_s=0.2)
            if not isinstance(bn_hex, str):
                last_err = f"eth_blockNumber returned non-str: {type(bn_hex)}"
            else:
                return hex_to_int(bn_hex), None
        except Exception as e:
            last_err = str(e)
        time.sleep(float(sleep_s))
    return None, last_err


def safe_get_block(
    rpc_url: str, number: int, retries: int = 5, sleep_s: float = 0.2
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    last_err: Optional[str] = None
    for i in range(max(1, int(retries))):
        try:
            b = rpc_call(
                rpc_url,
                "eth_getBlockByNumber",
                [hex(int(number)), False],
                retries=2,
                sleep_s=0.15,
            )
            if b is None:
                last_err = "eth_getBlockByNumber returned None"
            elif not isinstance(b, dict):
                last_err = f"eth_getBlockByNumber returned non-dict: {type(b)}"
            else:
                return b, None
        except Exception as e:
            last_err = str(e)
        time.sleep(float(sleep_s) * (1.5 ** i))
    return None, last_err


def fetch_blocks(rpc_url: str, out_path: str, start_bn: int, end_bn: int):
    for h in range(int(start_bn), int(end_bn) + 1):
        block, err = safe_get_block(rpc_url, h)
        if block is None:
            write_jsonl(out_path, {"blockNumber": h, "missing_block": True, "error": err})
            continue

        try:
            ts_hex = block.get("timestamp")
            if not isinstance(ts_hex, str):
                write_jsonl(out_path, {"blockNumber": h, "error": "missing/invalid timestamp field"})
                continue

            txs = block.get("transactions", [])
            tx_count = len(txs) if isinstance(txs, list) else 0

            write_jsonl(
                out_path,
                {
                    "blockNumber": h,
                    "blockTimestamp": hex_to_int(ts_hex),
                    "txCount": tx_count,
                },
            )
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

    # Default: fetch blocks after run (so analyze_run always has data)
    ap.add_argument("--fetch_blocks_after", action="store_true", default=True)
    ap.add_argument("--no_fetch_blocks_after", action="store_true", default=False)

    ap.add_argument("--sleep_suspect_ratio", type=float, default=1.2)

    args = ap.parse_args()

    if args.no_fetch_blocks_after:
        args.fetch_blocks_after = False

    rpc_dir = os.path.join(args.out, "rpc")
    ensure_dir(rpc_dir)

    blocks_path = os.path.join(rpc_dir, "blocks.jsonl")
    head_path = os.path.join(rpc_dir, "head.jsonl")
    peers_path = os.path.join(rpc_dir, "peers.jsonl")
    validators_path = os.path.join(rpc_dir, "validators.jsonl")
    meta_path = os.path.join(rpc_dir, "run_meta.json")

    ts_start_local = time.time()
    t0_m = time.monotonic()

    next_blocks_m = t0_m
    next_peers_m = t0_m
    next_validators_m = t0_m

    start_bn: Optional[int] = None
    end_bn: Optional[int] = None

    while True:
        now_m = time.monotonic()
        if now_m - t0_m >= int(args.duration):
            break

        now_local = time.time()

        if now_m >= next_blocks_m:
            try:
                bn_hex = rpc_call(args.rpc, "eth_blockNumber", [], retries=2, sleep_s=0.15)
                if not isinstance(bn_hex, str):
                    raise RuntimeError(f"eth_blockNumber returned non-str: {type(bn_hex)}")
                bn = hex_to_int(bn_hex)
                if start_bn is None:
                    start_bn = bn
                end_bn = bn
                write_jsonl(head_path, {"ts_local": now_local, "blockNumber": bn})
            except Exception as e:
                write_jsonl(head_path, {"ts_local": now_local, "error": str(e)})
            next_blocks_m = now_m + (1.0 / max(float(args.blocks_hz), 0.01))

        if now_m >= next_peers_m:
            try:
                pc_hex = rpc_call(args.rpc, "net_peerCount", [], retries=2, sleep_s=0.15)
                if not isinstance(pc_hex, str):
                    raise RuntimeError(f"net_peerCount returned non-str: {type(pc_hex)}")
                write_jsonl(peers_path, {"ts_local": now_local, "peerCount": hex_to_int(pc_hex)})
            except Exception as e:
                write_jsonl(peers_path, {"ts_local": now_local, "error": str(e)})
            next_peers_m = now_m + (1.0 / max(float(args.peers_hz), 0.01))

        if now_m >= next_validators_m:
            try:
                vals = rpc_call(
                    args.rpc,
                    "ibft_getValidatorsByBlockNumber",
                    ["latest"],
                    retries=2,
                    sleep_s=0.2,
                )
                if vals is None:
                    raise RuntimeError("ibft_getValidatorsByBlockNumber returned None")
                write_jsonl(validators_path, {"ts_local": now_local, "validators": vals})
            except Exception as e:
                write_jsonl(validators_path, {"ts_local": now_local, "error": str(e)})
            next_validators_m = now_m + (1.0 / max(float(args.validators_hz), 0.01))

        time.sleep(0.05)

    ts_end_local = time.time()
    t1_m = time.monotonic()

    end_bn_final, end_err = robust_read_block_number(args.rpc, float(args.end_read_budget_s))
    if end_bn_final is not None:
        end_bn = end_bn_final
        write_jsonl(head_path, {"ts_local": time.time(), "blockNumber_final": end_bn})
    else:
        write_jsonl(head_path, {"ts_local": time.time(), "end_blockNumber_error": end_err})

    duration_observed = t1_m - t0_m
    sleep_suspected = duration_observed > (int(args.duration) * max(1.0, float(args.sleep_suspect_ratio)))

    meta = {
        "ts_start_local": ts_start_local,
        "ts_end_local": ts_end_local,
        "duration_s_target": int(args.duration),
        "duration_s_observed": duration_observed,
        "sleep_suspected": bool(sleep_suspected),
        "sleep_suspect_ratio": float(args.sleep_suspect_ratio),
        "start_blockNumber": start_bn,
        "end_blockNumber": end_bn,
        "rpc": args.rpc,
        "fetch_blocks_after": bool(args.fetch_blocks_after),
        "end_read_budget_s": float(args.end_read_budget_s),
    }
    write_json(meta_path, meta)

    if args.fetch_blocks_after and start_bn is not None and end_bn is not None and end_bn >= start_bn:
        fetch_t0_m = time.monotonic()
        fetch_started_local = time.time()

        if os.path.exists(blocks_path):
            os.remove(blocks_path)

        fetch_blocks(args.rpc, blocks_path, start_bn, end_bn)

        fetch_finished_local = time.time()
        fetch_t1_m = time.monotonic()

        meta2 = dict(meta)
        meta2.update(
            {
                "fetch_started_local": fetch_started_local,
                "fetch_finished_local": fetch_finished_local,
                "fetch_duration_s": fetch_t1_m - fetch_t0_m,
                "fetched_blocks_expected": (end_bn - start_bn + 1),
            }
        )
        write_json(meta_path, meta2)


if __name__ == "__main__":
    main()