import json
from eth_account import Account

Account.enable_unaudited_hdwallet_features()

N = 4
out = []
for i in range(N):
    acct = Account.create()
    out.append({
        "name": f"load{i+1}",
        "address": acct.address,
        "private_key": acct.key.hex(),
    })

print(json.dumps(out, indent=2))