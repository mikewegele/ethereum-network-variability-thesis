import argparse
import json
import os
import time
import urllib.request

from eth_account import Account
from eth_utils import to_checksum_address


def rpc_call(url: str, method: str, params):
    payload = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        if "error" in data:
            raise RuntimeError(str(data["error"]))
        return data["result"]


def hex_to_int(x: str) -> int:
    return int(x, 16)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rpc", default="http://localhost:8545")
    ap.add_argument("--pk", required=True)
    ap.add_argument("--to", required=True)
    ap.add_argument("--rate", type=float, default=10.0)
    ap.add_argument("--value_wei", type=int, default=1)
    ap.add_argument("--gas", type=int, default=21000)
    ap.add_argument("--gas_price_wei", type=int, default=1_000_000_000)
    ap.add_argument("--chain_id", type=int, default=1337)
    ap.add_argument("--max_inflight", type=int, default=32)
    ap.add_argument("--refresh_s", type=float, default=1.0)
    ap.add_argument("--data_bytes", type=int, default=0, help="calldata size per tx (0 = no data)")
    ap.add_argument("--data_fill", choices=["zero", "rand"], default="rand")
    args = ap.parse_args()

    pk = args.pk.lower().strip()
    if pk.startswith("0x"):
        pk = pk[2:]

    acct = Account.from_key(pk)
    from_addr = to_checksum_address(acct.address)
    to_addr = to_checksum_address(args.to)

    if args.data_bytes < 0:
        raise SystemExit("--data_bytes must be >= 0")

    if args.data_bytes == 0:
        data_hex = None
    else:
        if args.data_fill == "zero":
            data = b"\x00" * args.data_bytes
        else:
            data = os.urandom(args.data_bytes)
        data_hex = "0x" + data.hex()

        worst_case = 21000 + 16 * args.data_bytes
        if args.gas < worst_case:
            args.gas = worst_case

    print("from", from_addr)
    print("to  ", to_addr)
    print("rate", args.rate, "data_bytes", args.data_bytes, "gas", args.gas, "max_inflight", args.max_inflight)

    def get_nonce(tag: str) -> int:
        return hex_to_int(rpc_call(args.rpc, "eth_getTransactionCount", [from_addr, tag]))

    latest_nonce = get_nonce("latest")
    pending_nonce = get_nonce("pending")

    # IMPORTANT FIX:
    # Always start from pending nonce to avoid creating "future-only" pools that are not executable.
    next_nonce = pending_nonce

    print("latest_nonce", latest_nonce, "pending_nonce", pending_nonce, "next_nonce", next_nonce)

    interval = 1.0 / max(args.rate, 0.01)
    sent = 0
    failed = 0
    throttled = 0
    t0 = time.time()
    next_t = t0
    last_refresh = t0

    while True:
        now = time.time()

        if now - last_refresh >= args.refresh_s:
            try:
                latest_nonce = get_nonce("latest")
                pending_nonce = get_nonce("pending")
                # Keep next_nonce aligned to pending to avoid gaps.
                if next_nonce < pending_nonce:
                    next_nonce = pending_nonce
            except Exception:
                pass
            last_refresh = now

        backlog = pending_nonce - latest_nonce
        if backlog >= args.max_inflight:
            throttled += 1
            time.sleep(0.05)
            continue

        if now < next_t:
            time.sleep(min(0.05, next_t - now))
            continue
        next_t = now + interval

        tx = {
            "nonce": next_nonce,
            "to": to_addr,
            "value": args.value_wei,
            "gas": args.gas,
            "gasPrice": args.gas_price_wei,
            "chainId": args.chain_id,
        }
        if data_hex is not None:
            tx["data"] = data_hex

        try:
            signed = Account.sign_transaction(tx, private_key=pk)
            raw = "0x" + signed.raw_transaction.hex()
            rpc_call(args.rpc, "eth_sendRawTransaction", [raw])
            sent += 1
            next_nonce += 1
        except Exception as e:
            failed += 1
            # On any failure, refresh nonces and re-align to pending.
            try:
                latest_nonce = get_nonce("latest")
                pending_nonce = get_nonce("pending")
                if next_nonce < pending_nonce:
                    next_nonce = pending_nonce
            except Exception:
                pass

            if failed % 10 == 0:
                print("failures", failed, "last_err", str(e))

        if (sent + failed) % 200 == 0:
            dt = max(0.001, time.time() - t0)
            print(
                "sent", sent,
                "failed", failed,
                "latest", latest_nonce,
                "pending", pending_nonce,
                "backlog", (pending_nonce - latest_nonce),
                "next", next_nonce,
                "eff_tps", round(sent / dt, 2),
                "throttled_loops", throttled,
            )


if __name__ == "__main__":
    main()