# Trident MCP (TRON)

Minimal FastMCP stdio server that exposes a handful of TRON helpers as MCP tools. Runs fully on Python stdlib plus `fastmcp`, and ships a colored CLI agent for interactive use.

## What it can do
- `get_usdt_balance(address)` — TRC20 USDT balance from TRONSCAN.
- `get_network_params()` — chain fee parameters from TRONGRID.
- `get_tx_status(txid)` — transaction confirmation + receipt summary from TRONGRID.
- `get_recent_transactions(address, limit)` — latest account tx list (TRONGRID primary, TRONSCAN fallback).
- `get_trc20_transfers(address, limit)` — latest TRC20 transfers for an address (same fallback).
- `get_address_labels(address)` — labels/flags from TRONSCAN (contract, shielded, name, tags).

## Quick start
```bash
cd ~/Documents/ctf/blockchain/program/HK_hacker_26/trident-mcp
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt      # installs fastmcp and deps
```

Run the MCP server (stdio, no HTTP port):
```bash
python run.py
```

Use the colorful CLI agent (multi‑turn, auto tool-calls):
```bash
python -m agents.agent_runner
# or single prompt:
python -m agents.agent_runner --prompt "Show me TRON energy and bandwidth fees."
# debug模式(打印LLM请求/响应)： 
python -m agents.agent_runner --debug --prompt "List the last 5 transactions for address THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF."
```

Optional Textual TUI (if you want a paneled UI; otherwise ignore):
```bash
pip install textual
python -m agents.tui_app
```

JSON-RPC (if you connect through a bridge):
```bash
curl -X POST http://localhost:8787/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"list_tools"}'
```

## Configuration
`config.toml` is read first, then env vars override:
```
PORT                     (port)
TRONSCAN_BASE            (default https://apilist.tronscanapi.com/api)
TRONGRID_BASE            (default https://api.trongrid.io)
TRONGRID_API_KEY | TRON_PRO_API_KEY
TRONSCAN_API_KEY         (for TRC20 transfers/address labels fallback)
TRON_USDT_CONTRACT       (default TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t)
REQUEST_TIMEOUT_MS
LOG_LEVEL, LOG_FILE
AI_API_BASE, AI_API_KEY, AI_MODEL, AI_PROVIDER  # optional for LLM features
SAFETY_ENABLE            (true/false)
```

## Repo map (essentials)
- `run.py` — FastMCP entrypoint; registers tools, starts stdio server.
- `tron_mcp/tools.py` — tool logic & validation.
- `tron_mcp/tron_api.py` — HTTP helpers to TRONSCAN/TRONGRID.
- `tron_mcp/safety.py` — optional `_human_notes` annotator for hashes/addresses.
- `tron_mcp/settings.py` — loads config.toml + env overrides.
- `tron_mcp/ai/client.py` — generic chat client for OpenAI/DeepSeek/Anthropic/etc.
- `agents/agent_runner.py` — colored CLI agent (recommended).
- `agents/ai_llm_tool_call.py` — minimal LLM call demo.
- `agents/tui_app.py` — Textual TUI (optional).
- `tool_smoke.py` — quick CLI smoke for the core tools (network/usdt/tx_status).

## Notes
- Pure stdlib networking; no local node needed. Network connectivity to TRONSCAN/TRONGRID is required for live data.
- Safety enrichment is on by default; set `SAFETY_ENABLE=false` to remove `_human_notes`.
- Keep your `ai_api_key` out of the repo; use env vars for secrets.

## Handy prompts (REPL / agent_runner)
- Q1: “Show me the current TRON network energy fee and bandwidth fee.”
- Q2: “Check the USDT balance of TPwjKc2nfSb6Zxk4sZDSZu6f9QaK3xktAP.”
- Q3: “Is transaction 17c46bf2625aaf21b28a0c54783715d63380ccdb3d1134c8365e2f6c4 confirmed?”
- Q4: “List the last 5 transactions for address THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF.”
- Q5: “Show the latest 5 TRC20 transfers involving address THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF.”
- Q6: “What labels or flags does TRON address THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF have?”
