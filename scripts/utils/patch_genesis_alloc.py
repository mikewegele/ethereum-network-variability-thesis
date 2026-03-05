import argparse
import json
import os

DEFAULT_BALANCE_HEX = "0x3635C9ADC5DEA00000"  # 1000 ETH

def norm_addr(a: str) -> str:
    a = a.strip()
    if a.startswith("0x"):
        a = a[2:]
    return "0x" + a.lower()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--genesis", default="config/genesis.json")
    ap.add_argument("--accounts", default="experiments/load_accounts.json")
    ap.add_argument("--balance_hex", default=DEFAULT_BALANCE_HEX)
    ap.add_argument("--also_fund", action="append", default=[], help="extra address to fund (can be repeated)")
    args = ap.parse_args()

    with open(args.genesis, "r", encoding="utf-8") as f:
        g = json.load(f)

    alloc = g.get("alloc")
    if alloc is None or not isinstance(alloc, dict):
        alloc = {}
        g["alloc"] = alloc

    with open(args.accounts, "r", encoding="utf-8") as f:
        accs = json.load(f)

    addrs = [a["address"] for a in accs if "address" in a]
    addrs += args.also_fund

    for addr in addrs:
        alloc[norm_addr(addr)] = {"balance": args.balance_hex}

    with open(args.genesis, "w", encoding="utf-8") as f:
        json.dump(g, f, indent=2)

    print(f"patched {args.genesis}")
    print("funded:")
    for addr in addrs:
        print(" -", norm_addr(addr))

if __name__ == "__main__":
    main()