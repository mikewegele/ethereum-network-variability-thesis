import argparse
import json
import time
import urllib.request


def rpc_call(url: str, method: str, params):
    payload = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        if "error" in data:
            raise RuntimeError(str(data["error"]))
        return data["result"]


def hex_to_int(x: str) -> int:
    return int(x, 16)


def write_jsonl(path: str, obj: dict):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rpc", default="http://localhost:8545")
    ap.add_argument("--out", required=True)
    ap.add_argument("--start", type=int, required=True)
    ap.add_argument("--end", type=int, required=True)
    ap.add_argument("--sleep_s", type=float, default=0.0)
    args = ap.parse_args()

    start = int(args.start)
    end = int(args.end)
    if end < start:
        raise SystemExit("--end must be >= --start")

    for h in range(start, end + 1):
        try:
            block = rpc_call(args.rpc, "eth_getBlockByNumber", [hex(h), False])
            write_jsonl(
                args.out,
                {
                    "blockNumber": h,
                    "blockTimestamp": hex_to_int(block["timestamp"]),
                    "txCount": len(block.get("transactions", [])),
                },
            )
        except Exception as e:
            write_jsonl(args.out, {"blockNumber": h, "error": str(e)})
        if args.sleep_s > 0:
            time.sleep(args.sleep_s)


if __name__ == "__main__":
    main()