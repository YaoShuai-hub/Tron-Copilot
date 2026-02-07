# 🚀 Trident MCP (TRON)

轻量级 FastMCP stdio 服务器 + 彩色 CLI Agent，帮你快速查询 TRON 费用、USDT 余额、交易状态、TRC20 转账与地址标签。纯 Python，零本地节点依赖。

## ✨ 亮点
- 🔌 即插即用：安装依赖即可跑；stdio MCP 兼容。
- 🛡️ 双源容错：TRONGRID 主用，TRONSCAN 备援（交易/转账）。
- 🤖 LLM 编排：可选接入 DeepSeek/OpenAI/Anthropic，自动 tool-call。
- 🌈 友好 UI：彩色 CLI Agent，支持 `--debug` 查看 LLM 往返。

## 🧰 可用工具
| 工具 | 作用 | 数据源 | 备注 |
| --- | --- | --- | --- |
| `get_network_params` | 网络能量/带宽/建号费用等 | TRONGRID | 费用基线 |
| `get_usdt_balance(address)` | TRC20 USDT 余额 | TRONSCAN | 可含 `_human_notes` |
| `get_tx_status(txid)` | 交易确认 + 收据 | TRONGRID | 64 hex |
| `get_recent_transactions(address, limit)` | 最近交易列表 | TRONGRID → TRONSCAN | 主备切换 |
| `get_trc20_transfers(address, limit)` | 最近 TRC20 转账 | TRONGRID → TRONSCAN | 主备切换 |
| `get_address_labels(address)` | 地址名称/标签/是否合约/是否屏蔽 | TRONSCAN | 标签查询 |
| `get_token_balance(address, token)` | 任意币种余额（TRX/TRC20） | TRONSCAN | symbol/合约 |
| `get_total_value(address, currency)` | 所有币种总价值 | TRONSCAN + CoinGecko | usd/cny |

## ⚡ 快速开始
```bash
cd ~/Documents/ctf/blockchain/program/HK_hacker_26/trident-mcp
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
```

运行 MCP 服务器（stdio）：
```bash
python3 run.py
```

彩色 CLI Agent（自动多轮工具调用）：
```bash
python3 -m agents.agent_runner
# 单句：
python3 -m agents.agent_runner --prompt "Show me TRON energy and bandwidth fees."
# 调试（打印 LLM 请求/响应）：
python3 -m agents.agent_runner --debug --prompt "List the last 5 transactions for address THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF."
```

可选 Textual TUI：
```bash
pip3 install textual
python3 -m agents.tui_app
```

JSON-RPC 示例（若通过桥接）：
```bash
curl -X POST http://localhost:8787/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"list_tools"}'
```

## 🔧 配置 (config.toml / 环境变量)
```
PORT
TRONSCAN_BASE      (默认 https://apilist.tronscanapi.com/api)
TRONGRID_BASE      (默认 https://api.trongrid.io)
TRONSCAN_API_KEY   (TRC20/labels 备份查询)
TRONGRID_API_KEY | TRON_PRO_API_KEY
TRON_USDT_CONTRACT (默认 TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t)
COINGECKO_BASE     (默认 https://api.coingecko.com/api/v3)
REQUEST_TIMEOUT_MS
LOG_LEVEL, LOG_FILE
AI_API_BASE, AI_API_KEY, AI_MODEL, AI_PROVIDER  # 可选，启用 LLM 编排
SAFETY_ENABLE      (true/false，控制 _human_notes)
```
👉 建议把真实 key 放 `.env`（已在 `.gitignore`），示例见 `.env.example`。

## 📂 目录速览
- `run.py` — FastMCP 入口。
- `tron_mcp/tools.py` — 工具实现与校验。
- `tron_mcp/tron_api.py` — TRONSCAN/TRONGRID HTTP helper（自动附加 API key）。
- `tron_mcp/safety.py` — `_human_notes` 注释器。
- `tron_mcp/settings.py` — 读取 config.toml + env。
- `tron_mcp/ai/client.py` — LLM 客户端（OpenAI/DeepSeek/Anthropic 等）。
- `agents/agent_runner.py` — 彩色 CLI agent（推荐）。
- `agents/ai_llm_tool_call.py` — 极简 LLM demo。
- `agents/tui_app.py` — Textual TUI（可选）。
- `tool_smoke.py` — 快速烟测脚本。

## 💬 常用提示 (REPL / agent_runner 可直接粘贴)
- Q1: Show me the current TRON network energy fee and bandwidth fee.
- Q2: Check the USDT balance of TPwjKc2nfSb6Zxk4sZDSZu6f9QaK3xktAP.
- Q3: Is transaction 17c46bf2625aaf21b28a0c54783715d63380ccdb3d1134c8365e2f6c4 confirmed?
- Q4: List the last 5 transactions for address THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF.
- Q5: Show the latest 5 TRC20 transfers involving address THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF.
- Q6: What labels or flags does TRON address THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF have?

## 🧭 排障小抄
- 400/401：检查 TRONSCAN/TRONGRID API key 是否有效或控制台是否限制来源。
- 没有 `_human_notes`：确认 `SAFETY_ENABLE` 未被设为 false。
- LLM 405/超时：加 `--debug` 看往返；必要时依赖本地 fallback（工具结果仍会显示）。
