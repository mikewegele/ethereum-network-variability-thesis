import argparse
import json
import os
import random
import time
import urllib.request
from typing import Any, Optional, Tuple

from eth_account import Account
from eth_utils import to_checksum_address


def rpc_call(
    url: str,
    method: str,
    params,
    timeout_s: float = 10.0,
    retries: int = 5,
    sleep_s: float = 0.2,
) -> Any:
    last_err: Optional[Exception] = None
    payload = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode("utf-8")

    for i in range(max(1, retries)):
        try:
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if "error" in data:
                raise RuntimeError(str(data["error"]))
            return data.get("result")
        except Exception as e:
            last_err = e
            if i < retries - 1:
                # exponential backoff + tiny jitter
                backoff = sleep_s * (1.6 ** i)
                backoff *= 1.0 + random.random() * 0.2
                time.sleep(backoff)

    raise RuntimeError(str(last_err) if last_err is not None else "rpc_call failed")


def hex_to_int(x: str) -> int:
    return int(x, 16)


def get_latest_block(rpc_url: str, retries: int = 6) -> Optional[dict]:
    try:
        b = rpc_call(rpc_url, "eth_getBlockByNumber", ["latest", False], retries=retries, sleep_s=0.2)
        return b if isinstance(b, dict) else None
    except Exception:
        return None


def get_base_fee_wei(rpc_url: str, last_base: int) -> int:
    b = get_latest_block(rpc_url)
    if not b:
        return last_base
    base_hex = b.get("baseFeePerGas")
    if base_hex is None:
        # pre-London or baseFee disabled -> keep last (often 0)
        return last_base
    try:
        return hex_to_int(base_hex)
    except Exception:
        return last_base


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
    ap.add_argument("--data_bytes", type=int, default=0)
    ap.add_argument("--data_fill", choices=["zero", "rand"], default="rand")

    # EIP-1559 fees
    ap.add_argument("--priority_fee_wei", type=int, default=1_000_000)
    ap.add_argument("--max_fee_wei", type=int, default=None)

    # run control
    ap.add_argument("--duration_s", type=float, default=None)
    ap.add_argument("--max_txs", type=int, default=None)

    # fallback mode if baseFee missing (pre-London)
    ap.add_argument("--legacy_if_no_basefee", action="store_true", default=True)
    ap.add_argument("--gas_price_wei", type=int, default=1_000_000)

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
        data = (b"\x00" * args.data_bytes) if args.data_fill == "zero" else os.urandom(args.data_bytes)
        data_hex = "0x" + data.hex()
        worst_case = 21000 + 16 * args.data_bytes
        if args.gas < worst_case:
            args.gas = worst_case

    def get_nonce(tag: str) -> int:
        r = rpc_call(args.rpc, "eth_getTransactionCount", [from_addr, tag], retries=6, sleep_s=0.2)
        return hex_to_int(r)

    def compute_fees(last_base: int) -> Tuple[int, int, int]:
        base = get_base_fee_wei(args.rpc, last_base)
        prio = max(0, int(args.priority_fee_wei))
        if args.max_fee_wei is None:
            max_fee = base * 2 + prio
        else:
            max_fee = int(args.max_fee_wei)
        if max_fee < base + prio:
            max_fee = base + prio
        return base, prio, max_fee

    # initial state
    last_base = 0
    base_fee, prio_fee, max_fee = compute_fees(last_base)
    last_base = base_fee

    latest_nonce = get_nonce("latest")
    pending_nonce = get_nonce("pending")
    next_nonce = max(latest_nonce, pending_nonce)

    print("from", from_addr)
    print("to  ", to_addr)
    print("rate", args.rate, "data_bytes", args.data_bytes, "gas", args.gas)
    print("chain latest_nonce", latest_nonce, "pending_nonce", pending_nonce, "next_nonce", next_nonce)
    print("fees_wei base", base_fee, "prio", prio_fee, "max", max_fee, "legacy_if_no_basefee", args.legacy_if_no_basefee)

    interval = 1.0 / max(args.rate, 0.01)
    sent = 0
    failed = 0
    throttled = 0

    t0 = time.time()
    next_t = t0
    last_refresh = 0.0  # force refresh immediately

    # keep these current for backlog checks
    latest_nonce_seen = latest_nonce
    pending_nonce_seen = pending_nonce

    while True:
        now = time.time()

        if args.duration_s is not None and (now - t0) >= float(args.duration_s):
            break
        if args.max_txs is not None and sent >= int(args.max_txs):
            break

        # refresh chain state
        if (now - last_refresh) >= args.refresh_s:
            try:
                latest_nonce_seen = get_nonce("latest")
                pending_nonce_seen = get_nonce("pending")
                if next_nonce < latest_nonce_seen:
                    next_nonce = latest_nonce_seen
                if next_nonce < pending_nonce_seen:
                    next_nonce = pending_nonce_seen

                base_fee, prio_fee, max_fee = compute_fees(last_base)
                last_base = base_fee
            except Exception as e:
                # don't die on refresh hiccup; keep running with last known values
                if failed % 10 == 0:
                    print("WARN refresh_error", str(e))
            last_refresh = now

        backlog = max(0, pending_nonce_seen - latest_nonce_seen)
        if backlog >= args.max_inflight:
            throttled += 1
            time.sleep(0.05)
            continue

        if now < next_t:
            time.sleep(min(0.05, next_t - now))
            continue
        next_t = now + interval

        # build tx (EIP-1559 if baseFee known; else legacy if enabled)
        tx = {
            "nonce": next_nonce,
            "to": to_addr,
            "value": args.value_wei,
            "gas": args.gas,
            "chainId": args.chain_id,
        }
        if data_hex is not None:
            tx["data"] = data_hex

        use_1559 = True
        latest_block = get_latest_block(args.rpc, retries=2)
        if not latest_block or latest_block.get("baseFeePerGas") is None:
            use_1559 = False

        if use_1559:
            tx["type"] = 2
            tx["maxPriorityFeePerGas"] = prio_fee
            tx["maxFeePerGas"] = max_fee
        else:
            if args.legacy_if_no_basefee:
                tx["gasPrice"] = int(args.gas_price_wei)
            else:
                # still send type2 with fee=prio (keeps format consistent)
                tx["type"] = 2
                tx["maxPriorityFeePerGas"] = prio_fee
                tx["maxFeePerGas"] = prio_fee

        try:
            signed = Account.sign_transaction(tx, private_key=pk)
            raw = "0x" + signed.raw_transaction.hex()
            rpc_call(args.rpc, "eth_sendRawTransaction", [raw], retries=5, sleep_s=0.15)
            sent += 1
            next_nonce += 1
        except Exception as e:
            failed += 1
            # resync nonce pointers occasionally
            try:
                latest_nonce_seen = get_nonce("latest")
                pending_nonce_seen = get_nonce("pending")
                next_nonce = max(next_nonce, latest_nonce_seen, pending_nonce_seen)
            except Exception:
                pass
            if failed % 10 == 0:
                print("failures", failed, "last_err", str(e))

        if (sent + failed) % 200 == 0:
            dt = max(0.001, time.time() - t0)
            print(
                "sent", sent,
                "failed", failed,
                "latest", latest_nonce_seen,
                "pending", pending_nonce_seen,
                "backlog", max(0, pending_nonce_seen - latest_nonce_seen),
                "next", next_nonce,
                "eff_tps", round(sent / dt, 2),
                "throttled_loops", throttled,
                "baseFee", base_fee,
                "prioFee", prio_fee,
                "maxFee", max_fee,
                "mode", ("1559" if use_1559 else "legacy")
            )

    dt = max(0.001, time.time() - t0)
    print("done sent", sent, "failed", failed, "eff_tps", round(sent / dt, 2))


if __name__ == "__main__":
    main()