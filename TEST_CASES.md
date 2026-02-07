# Trident MCP Test Cases

This is a consolidated, runnable test checklist for all tools.

**Notes**

- Default network is Nile testnet.
- `TRONSCAN_BASE` must include `/api`: `https://nileapi.tronscan.org/api`.
- Read-only tools can run with sample addresses.
- Transaction tools require real addresses and balances.

## 0) Environment

Optional overrides:

```bash
export TRONGRID_BASE=https://nile.trongrid.io
export TRONSCAN_BASE=https://nileapi.tronscan.org/api
```

If you want mainnet:

```bash
export TRONGRID_BASE=https://api.trongrid.io
export TRONSCAN_BASE=https://apilist.tronscanapi.com/api
```

## 1) Read-Only Tools (Safe to Run)

```bash
cd /home/henry/Documents/ctf/blockchain/program/HK_hacker_26/trident-mcp

# get_network_params
python3 -c "from tron_mcp import tools; print(tools.get_network_params())"

# get_usdt_balance
python3 -c "from tron_mcp import tools; print(tools.get_usdt_balance('TPwjKc2nfSb6Zxk4sZDSZu6f9QaK3xktAP'))"

# get_trx_balance
python3 -c "from tron_mcp import tools; print(tools.get_trx_balance('TUe5xktiJcM4fMzR9yGet3jma5BJoT43jH'))"

# get_tx_status (Nile sample txid)
python3 -c "from tron_mcp import tools; print(tools.get_tx_status('e191f1114cbd8cbe43452b2c3141326ae4c2aba22a82ba195c9573895cbbfd84'))"

# get_recent_transactions
python3 -c "from tron_mcp import tools; print(tools.get_recent_transactions('THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF', limit=5))"

# get_trc20_transfers
# NOTE: Nile addresses may return empty results. If so, use mainnet sample below.
python3 -c "from tron_mcp import tools; print(tools.get_trc20_transfers('THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF', limit=5))"

# Mainnet sample (set TRONGRID_BASE/TRONSCAN_BASE to mainnet first)
python3 -c "from tron_mcp import tools; print(tools.get_trc20_transfers('TY1KW15Ds7JxbvMVpDd6aHbyV9cv9dDuuH', limit=5))"

# get_address_labels
python3 -c "from tron_mcp import tools; print(tools.get_address_labels('THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF'))"
```

## 2) TRX Unsigned Transfer (Requires Real Addresses)

Set real addresses with balance:

```bash
export FROM_ADDR=YOUR_REAL_FROM_ADDRESS
export TO_ADDR=YOUR_REAL_TO_ADDRESS
```

Run:

```bash
python3 -c "from tron_mcp.extensions.tx_assistant import create_unsigned_trx_transfer; print(create_unsigned_trx_transfer('$FROM_ADDR','$TO_ADDR',amount_trx='1.25'))"
```

## 3) TRC20 Unsigned Transfer (Requires Real Addresses + Token Balance)

If you have USDT on testnet:

```bash
python3 -c "from tron_mcp.extensions.trc20_assistant import create_unsigned_trc20_transfer; print(create_unsigned_trc20_transfer('$FROM_ADDR','$TO_ADDR',amount='1.5',decimals=6))"
```

If you know raw units:

```bash
python3 -c "from tron_mcp.extensions.trc20_assistant import create_unsigned_trc20_transfer; print(create_unsigned_trc20_transfer('$FROM_ADDR','$TO_ADDR',amount_raw='1500000'))"
```

## 4) Agent Pipeline (Human-in-the-loop)

Intent parsing:

```bash
python3 -c "from tron_mcp.extensions.agent_pipeline import parse_intent; print(parse_intent('send 1.25 TRX from $FROM_ADDR to $TO_ADDR'))"
```

Prepare transaction (confirmation + unsigned tx):

```bash
python3 -c "from tron_mcp.extensions.agent_pipeline import prepare_transaction; print(prepare_transaction('send 1.25 TRX from $FROM_ADDR to $TO_ADDR'))"
```

Request signature (no private keys are used/stored):

```bash
python3 - <<'PY'
from tron_mcp.extensions.agent_pipeline import prepare_transaction, request_signature
import os
prompt = f"send 1.25 TRX from {os.environ.get('FROM_ADDR')} to {os.environ.get('TO_ADDR')}"
res = prepare_transaction(prompt)
print(request_signature(res.get('unsigned_tx')))
PY
```

Broadcast signed transaction (requires signed tx):

```bash
python3 -c "from tron_mcp.extensions.agent_pipeline import broadcast_signed; print(broadcast_signed({'txID':'...','signature':['...'],'raw_data':{...}}))"
```

## 5) MCP JSON-RPC Example

```bash
curl -X POST http://localhost:8787/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"call_tool","params":{"name":"agent_prepare_transaction","args":{"prompt":"send 1.25 TRX from '$FROM_ADDR' to '$TO_ADDR'"}}}'
```
