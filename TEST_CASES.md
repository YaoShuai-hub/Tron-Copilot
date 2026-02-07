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

## 1) Core TRON 查询（只读安全）

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

## 2) TRON 交易构建/签名

### 2.1) TRX Unsigned Transfer (Requires Real Addresses)

Set real addresses with balance:

```bash
export FROM_ADDR=YOUR_REAL_FROM_ADDRESS
export TO_ADDR=YOUR_REAL_TO_ADDRESS
```

Run:

```bash
python3 -c "from tron_mcp.extensions.tx_assistant import create_unsigned_trx_transfer; print(create_unsigned_trx_transfer('$FROM_ADDR','$TO_ADDR',amount_trx='1.25'))"
```

### 2.2) TRC20 Unsigned Transfer (Requires Real Addresses + Token Balance)

If you have USDT on testnet:

```bash
python3 -c "from tron_mcp.extensions.trc20_assistant import create_unsigned_trc20_transfer; print(create_unsigned_trc20_transfer('$FROM_ADDR','$TO_ADDR',amount='1.5',decimals=6))"
```

If you know raw units:

```bash
python3 -c "from tron_mcp.extensions.trc20_assistant import create_unsigned_trc20_transfer; print(create_unsigned_trc20_transfer('$FROM_ADDR','$TO_ADDR',amount_raw='1500000'))"
```

### 2.3) Full TRX Transfer Flow (Generate → Sign → Broadcast → Confirm)

```bash
cd /home/henry/Documents/ctf/blockchain/program/HK_hacker_26/trident-mcp

# 1) Generate unsigned transaction
python3 - <<'PY'
import json
from tron_mcp.extensions.tx_assistant import create_unsigned_trx_transfer

from_addr = "TUe5xktiJcM4fMzR9yGet3jma5BJoT43jH"
to_addr = "TM7S769qMobxfuvN73ASpyuwZUQS29JZmC"

tx = create_unsigned_trx_transfer(from_addr, to_addr, amount_trx="1.25")
with open("unsigned_tx.json", "w") as f:
    json.dump(tx["unsignedTx"], f, ensure_ascii=False, indent=2)
print("new txid:", tx["txid"])
PY

# 2) Sign (reads TRON_PRIVATE_KEY from .env.private)
python3 - <<'PY'
import json
from tron_mcp.extensions.local_signer import sign_transaction

with open("unsigned_tx.json", "r") as f:
    unsigned = json.load(f)

signed = sign_transaction(unsigned)
with open("signed_tx.json", "w") as f:
    json.dump(signed["signed_tx"], f, ensure_ascii=False, indent=2)
print("signed txid:", signed["txid"])
PY

# 3) Broadcast signed transaction
python3 - <<'PY'
import json
from tron_mcp.extensions.agent_pipeline import broadcast_signed
with open("signed_tx.json", "r") as f:
    signed_tx = json.load(f)
print(broadcast_signed(signed_tx))
PY

# 4) Confirm transaction (replace with returned txid)
python3 -c "from tron_mcp import tools; print(tools.get_tx_status('YOUR_TXID'))"
```

### 2.4) Full TRX Transfer Flow (No Files, In-Memory Signing)

```bash
cd /home/henry/Documents/ctf/blockchain/program/HK_hacker_26/trident-mcp

python3 - <<'PY'
from tron_mcp.extensions.tx_assistant import create_unsigned_trx_transfer
from tron_mcp.extensions.local_signer import sign_transaction
from tron_mcp.extensions.agent_pipeline import broadcast_signed

from_addr = "TUe5xktiJcM4fMzR9yGet3jma5BJoT43jH"
to_addr = "TM7S769qMobxfuvN73ASpyuwZUQS29JZmC"

unsigned = create_unsigned_trx_transfer(from_addr, to_addr, amount_trx="1.25")
signed = sign_transaction(unsigned["unsignedTx"])
print("signed txid:", signed["txid"])

result = broadcast_signed(signed["signed_tx"])
print("broadcast:", result)
PY
```

## 3) Agent Pipeline (Human-in-the-loop)

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

## 4) 任务模块

### 4.1) Chain Ops

```bash
# chain_transfer_flow (build only)
python3 -c "from tron_mcp import tools; print(tools.call_tool('chain_transfer_flow', {'asset':'TRX','from_address':'TUe5xktiJcM4fMzR9yGet3jma5BJoT43jH','to_address':'TM7S769qMobxfuvN73ASpyuwZUQS29JZmC','amount':'1.25'}))"

# chain_tx_status
python3 -c "from tron_mcp import tools; print(tools.call_tool('chain_tx_status', {'txid':'e191f1114cbd8cbe43452b2c3141326ae4c2aba22a82ba195c9573895cbbfd84'}))"
```

### 4.2) Funds Flow (Deposit/Withdraw)

```bash
# prepare_deposit_withdraw (withdraw plan, onchain)
python3 -c "from tron_mcp import tools; print(tools.call_tool('prepare_deposit_withdraw', {'action':'withdraw','token':'TRX','amount':'1.25','from_address':'TUe5xktiJcM4fMzR9yGet3jma5BJoT43jH','to_address':'TM7S769qMobxfuvN73ASpyuwZUQS29JZmC'}))"
```

### 4.3) Audit Log (JSONL)

```bash
# audit_log_event
python3 -c "from tron_mcp import tools; print(tools.call_tool('audit_log_event', {'event': {'action':'test','detail':'hello'}}))"

# audit_get_logs
python3 -c "from tron_mcp import tools; print(tools.call_tool('audit_get_logs', {'limit': 5}))"

# audit_reconcile (replace with real txids)
python3 -c "from tron_mcp import tools; print(tools.call_tool('audit_reconcile', {'txids': ['e3c5359f08cf3e066638c1866e493f0528527624ab0341026d97d5d8c725e7a3']}))"
```

### 4.4) Telegram

```bash
# send_telegram (requires TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID)
python3 -c "from tron_mcp import tools; print(tools.call_tool('send_telegram', {'message':'test from trident-mcp'}))"

# telegram_subscribe (uses TELEGRAM_CHAT_ID)
python3 -c "from tron_mcp import tools; print(tools.call_tool('telegram_subscribe', {}))"

# telegram_list_subscribers
python3 -c "from tron_mcp import tools; print(tools.call_tool('telegram_list_subscribers', {}))"

# telegram_broadcast
python3 -c "from tron_mcp import tools; print(tools.call_tool('telegram_broadcast', {'message':'broadcast test'}))"

# telegram_unsubscribe
python3 -c "from tron_mcp import tools; print(tools.call_tool('telegram_unsubscribe', {}))"
```

### 4.5) Market Data (Orderbook / Kline)

```bash
# get_orderbook
python3 -c "from tron_mcp import tools; print(tools.call_tool('get_orderbook', {'symbol':'BTCUSDT','limit':10}))"

# get_kline
python3 -c "from tron_mcp import tools; print(tools.call_tool('get_kline', {'symbol':'BTCUSDT','interval':'1m','limit':5}))"

# notify via Telegram (broadcast to subscribers)
python3 -c "from tron_mcp import tools; print(tools.call_tool('get_orderbook', {'symbol':'BTCUSDT','limit':5,'notify':True,'broadcast':True}))"
```

### 4.6) Exchange Adapter (CCXT)

```bash
# Requires: pip install ccxt
# Set credentials in .env.private (EXCHANGE_ID / EXCHANGE_API_KEY / EXCHANGE_SECRET / EXCHANGE_PASSWORD)
# Optional for binance (域名替换): EXCHANGE_API_DOMAIN=api1.binance.com
# Optional for binance (代理): EXCHANGE_PROXY=http://127.0.0.1:7890

# get balance
python3 -c "from tron_mcp import tools; print(tools.call_tool('exchange_get_balance', {'exchange_id':'binance'}))"

# get deposit address (example: USDT TRC20)
python3 -c "from tron_mcp import tools; print(tools.call_tool('exchange_get_deposit_address', {'exchange_id':'binance','currency':'USDT','network':'TRC20'}))"

# create order (example, may require sandbox on some exchanges)
python3 -c "from tron_mcp import tools; print(tools.call_tool('exchange_create_order', {'exchange_id':'binance','symbol':'BTC/USDT','type':'market','side':'buy','amount':0.001}))"

# withdraw (DANGEROUS, requires whitelist/2FA on most exchanges)
python3 -c "from tron_mcp import tools; print(tools.call_tool('exchange_withdraw', {'exchange_id':'binance','currency':'USDT','amount':1,'address':'YOUR_ADDRESS','network':'TRC20'}))"

# fetch withdrawals
python3 -c "from tron_mcp import tools; print(tools.call_tool('exchange_fetch_withdrawals', {'exchange_id':'binance','currency':'USDT','limit':5}))"

# fetch deposits
python3 -c "from tron_mcp import tools; print(tools.call_tool('exchange_fetch_deposits', {'exchange_id':'binance','currency':'USDT','limit':5}))"

# withdraw (auto infer network for TRON address if network not provided)
python3 -c "from tron_mcp import tools; print(tools.call_tool('exchange_withdraw', {'exchange_id':'binance','currency':'USDT','amount':1,'address':'TXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'}))"
```
## 5) MCP JSON-RPC Example

```bash
curl -X POST http://localhost:8787/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"call_tool","params":{"name":"agent_prepare_transaction","args":{"prompt":"send 1.25 TRX from '$FROM_ADDR' to '$TO_ADDR'"}}}'
```
