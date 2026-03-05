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


def int_to_hex(x: int) -> str:
    return hex(int(x))


def get_latest_base_fee_wei(rpc_url: str, retries: int = 8, sleep_s: float = 0.25) -> int:
    last_err = None
    for _ in range(retries):
        try:
            b = rpc_call(rpc_url, "eth_getBlockByNumber", ["latest", False])
            if b is None:
                last_err = "latest block is None"
            else:
                return hex_to_int(b.get("baseFeePerGas", "0x0"))
        except Exception as e:
            last_err = str(e)
        time.sleep(sleep_s)

    # Fallback: treat as pre-London / baseFee unknown -> 0
    # (keeps the load generator running even if RPC glitches)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rpc", default="http://localhost:8545")
    ap.add_argument("--pk", required=True)
    ap.add_argument("--to", required=True)
    ap.add_argument("--rate", type=float, default=10.0)
    ap.add_argument("--value_wei", type=int, default=1)
    ap.add_argument("--gas", type=int, default=21000)
    ap.add_argument("--chain_id", type=int, default=1337)
    ap.add_argument("--max_inflight", type=int, default=32)
    ap.add_argument("--refresh_s", type=float, default=1.0)
    ap.add_argument("--data_bytes", type=int, default=0, help="calldata size per tx (0 = no data)")
    ap.add_argument("--data_fill", choices=["zero", "rand"], default="rand")

    ap.add_argument("--priority_fee_wei", type=int, default=1_000_000, help="maxPriorityFeePerGas (wei)")
    ap.add_argument("--max_fee_wei", type=int, default=None, help="maxFeePerGas (wei). If omitted: baseFee*2 + priority")

    ap.add_argument("--duration_s", type=float, default=None)
    ap.add_argument("--max_txs", type=int, default=None)

    args = ap.parse_args()

    pk = args.pk.strip().lower()
    if pk.startswith("0x"):
        pk = pk[2:]
    if len(pk) != 64:
        raise SystemExit("--pk must be 32 bytes hex (64 hex chars), with or without 0x")

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

    def get_nonce(tag: str) -> int:
        return hex_to_int(rpc_call(args.rpc, "eth_getTransactionCount", [from_addr, tag]))

    def compute_fees(last_base: int) -> tuple[int, int, int]:
        base = get_latest_base_fee_wei(args.rpc)
        if base == 0 and last_base > 0:
            # prefer last known baseFee if RPC glitched to 0
            base = last_base

        prio = int(args.priority_fee_wei)
        if prio < 0:
            prio = 0

        if args.max_fee_wei is None:
            max_fee = base * 2 + prio
        else:
            max_fee = int(args.max_fee_wei)

        if max_fee < base + prio:
            max_fee = base + prio

        return base, prio, max_fee

    base_fee = 0
    base_fee, prio_fee, max_fee = compute_fees(base_fee)

    print("from", from_addr)
    print("to  ", to_addr)
    print("rate", args.rate, "data_bytes", args.data_bytes, "gas", args.gas)
    print("fees_wei base", base_fee, "prio", prio_fee, "max", max_fee)

    latest_nonce = get_nonce("latest")
    pending_nonce = get_nonce("pending")
    next_nonce = max(latest_nonce, pending_nonce)

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

        if args.duration_s is not None and (now - t0) >= float(args.duration_s):
            break
        if args.max_txs is not None and sent >= int(args.max_txs):
            break

        if now - last_refresh >= args.refresh_s:
            latest_nonce = get_nonce("latest")
            pending_nonce = get_nonce("pending")
            if next_nonce < latest_nonce:
                next_nonce = latest_nonce
            if next_nonce < pending_nonce:
                next_nonce = pending_nonce

            base_fee, prio_fee, max_fee = compute_fees(base_fee)
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
            "type": 2,
            "nonce": next_nonce,
            "to": to_addr,
            "value": args.value_wei,
            "gas": args.gas,
            "maxPriorityFeePerGas": prio_fee,
            "maxFeePerGas": max_fee,
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
            try:
                latest_nonce = get_nonce("latest")
                pending_nonce = get_nonce("pending")
                next_nonce = max(next_nonce, latest_nonce, pending_nonce)
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
                "baseFee", base_fee,
                "prioFee", prio_fee,
                "maxFee", max_fee
            )

    dt = max(0.001, time.time() - t0)
    print("done sent", sent, "failed", failed, "eff_tps", round(sent / dt, 2))


if __name__ == "__main__":
    main()