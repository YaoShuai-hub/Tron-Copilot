# 🚀 Trident MCP (TRON)

轻量级 FastMCP stdio 服务器 + 彩色 CLI Agent，帮你快速查询 TRON 费用、USDT 余额、交易状态、TRC20 转账与地址标签。纯 Python，零本地节点依赖。

## ✨ 亮点
- 🔌 即插即用：安装依赖即可跑；stdio MCP 兼容。
- 🛡️ 双源容错：TRONGRID 主用，TRONSCAN 备援（交易/转账）。
- 🤖 LLM 编排：可选接入 DeepSeek/OpenAI/Anthropic，自动 tool-call。
- 🌈 友好 UI：彩色 CLI Agent，支持 `--debug` 查看 LLM 往返。

## 🧰 可用工具（按模块）

### 1) Core TRON 查询
| 工具 | 作用 | 数据源 | 备注 |
| --- | --- | --- | --- |
| `get_network_params` | 网络能量/带宽/建号费用等 | TRONGRID | 费用基线 |
| `get_trx_balance(address)` | TRX 余额 | TRONGRID | 基础账户余额 |
| `get_usdt_balance(address)` | TRC20 USDT 余额 | TRONSCAN | 可含 `_human_notes` |
| `get_tx_status(txid)` | 交易确认 + 收据 | TRONGRID | 64 hex |
| `get_recent_transactions(address, limit)` | 最近交易列表 | TRONGRID → TRONSCAN | 主备切换 |
| `get_trc20_transfers(address, limit)` | 最近 TRC20 转账 | TRONGRID → TRONSCAN | 主备切换 |
| `get_address_labels(address)` | 地址名称/标签/是否合约/是否屏蔽 | TRONSCAN | 标签查询 |

### 2) TRON 交易构建/签名
| 工具 | 作用 | 数据源 | 备注 |
| --- | --- | --- | --- |
| `create_unsigned_trx_transfer(from_address, to_address, amount_trx?, amount_sun?)` | 生成未签名 TRX 转账 | TRONGRID | 用户签名后广播 |
| `create_unsigned_trc20_transfer(from_address, to_address, token_contract?, amount?, amount_raw?, decimals?)` | 生成未签名 TRC20 转账 | TRONGRID | 用户签名后广播 |
| `sign_transaction(unsigned_tx, env_path?)` | 本地私钥签名 | 本地 | 读取 `.env.private` |
| `broadcast_signed_transaction(signed_tx)` | 广播已签名交易 | TRONGRID | 返回广播结果 |

### 3) Agent Pipeline
| 工具 | 作用 | 数据源 | 备注 |
| --- | --- | --- | --- |
| `agent_parse_intent(prompt)` | 解析自然语言意图 | 本地 | 启发式解析 |
| `agent_prepare_transaction(prompt)` | 生成确认摘要 + 未签名交易 | TRONGRID | 多层流程 |
| `agent_request_signature(unsigned_tx)` | 生成签名请求 | 本地 | 不保存私钥 |

### 4) 任务模块：链上与资金流
| 工具 | 作用 | 数据源 | 备注 |
| --- | --- | --- | --- |
| `chain_transfer_flow(...)` | 一站式转账（构建/签名/广播） | 混合 | 任务模块 |
| `chain_tx_status(txid)` | 交易状态（带 from/to） | TRONGRID | 任务模块 |
| `prepare_deposit_withdraw(...)` | 充值/提现规划 | 本地/链上 | 任务模块 |

### 5) 任务模块：市场数据
| 工具 | 作用 | 数据源 | 备注 |
| --- | --- | --- | --- |
| `get_orderbook(symbol?, limit?, notify?, chat_id?, broadcast?)` | 盘口快照 | REST | 任务模块 |
| `get_kline(symbol?, interval?, limit?, notify?, chat_id?, broadcast?)` | K线数据 | REST | 任务模块 |

### 6) 任务模块：交易所适配（CCXT）
| 工具 | 作用 | 数据源 | 备注 |
| --- | --- | --- | --- |
| `exchange_get_balance(...)` | 交易所余额（CCXT） | REST | 任务模块 |
| `exchange_get_asset_balance(...)` | 单币种余额查询（CCXT） | REST | 任务模块 |
| `exchange_get_deposit_address(...)` | 交易所充值地址（CCXT） | REST | 任务模块 |
| `exchange_withdraw(...)` | 交易所提现（CCXT） | REST | 任务模块 |
| `exchange_fetch_withdrawals(...)` | 交易所提现记录（CCXT） | REST | 任务模块 |
| `exchange_fetch_deposits(...)` | 交易所充值记录（CCXT） | REST | 任务模块 |
| `exchange_create_order(...)` | 交易所下单（CCXT） | REST | 任务模块 |
| `exchange_cancel_order(...)` | 交易所撤单（CCXT） | REST | 任务模块 |
| `exchange_fetch_order(...)` | 交易所查单（CCXT） | REST | 任务模块 |

### 7) 任务模块：风控与开仓辅助
| 工具 | 作用 | 数据源 | 备注 |
| --- | --- | --- | --- |
| `position_snapshot(...)` | 仓位/余额快照 | 交易所 | 任务模块 |
| `position_alerts(...)` | 仓位预警 | 交易所 | 任务模块 |
| `entry_assist(...)` | 开仓辅助（盘口/K线） | REST | 任务模块 |

### 8) 任务模块：链上资产监控
| 工具 | 作用 | 数据源 | 备注 |
| --- | --- | --- | --- |
| `onchain_snapshot(...)` | 链上余额快照 | TRONGRID/TRONSCAN | 任务模块 |
| `onchain_alerts(...)` | 链上变化预警 | TRONGRID/TRONSCAN | 任务模块 |

### 9) 任务模块：通知与审计
| 工具 | 作用 | 数据源 | 备注 |
| --- | --- | --- | --- |
| `send_telegram(message, ...)` | Telegram 通知 | Telegram | 任务模块 |
| `telegram_subscribe(chat_id?, label?)` | 订阅 Telegram | Telegram | 任务模块 |
| `telegram_unsubscribe(chat_id?)` | 取消订阅 Telegram | Telegram | 任务模块 |
| `telegram_list_subscribers()` | 查看订阅列表 | Telegram | 任务模块 |
| `telegram_broadcast(message, ...)` | 向订阅者群发 | Telegram | 任务模块 |
| `audit_log_event(event, path?)` | 写入审计日志 | 本地 | 任务模块 |
| `audit_get_logs(limit?, path?)` | 读取审计日志 | 本地 | 任务模块 |
| `audit_reconcile(txids, path?)` | 对账（查链上状态） | TRONGRID | 任务模块 |

### 10) 资产估值
| 工具 | 作用 | 数据源 | 备注 |
| --- | --- | --- | --- |
| `get_token_balance(address, token)` | 任意币种余额（TRX/TRC20） | TRONSCAN | symbol/合约 |
| `get_total_value(address, currency)` | 所有币种总价值 | TRONSCAN + CoinGecko | usd/cny |
| `run_bash_command(command, cwd?, timeout_sec?, max_output_chars?)` | 执行本地 bash 指令 | 本地 | 仅限仓库内路径 |

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

Telegram 交互式助手（本地启动）：
```bash
# 在 .env.private 中配置 TELEGRAM_BOT_TOKEN（以及可选 TELEGRAM_CHAT_ID / TELEGRAM_ALLOW_ALL）
python3 -m agents.telegram_bot
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

交易所适配工具（CCXT）需要额外安装：
```bash
pip3 install ccxt
```
配置凭证（写入 `.env.private`）：
```
EXCHANGE_ID=binance
EXCHANGE_API_KEY=your_api_key
EXCHANGE_SECRET=your_secret
EXCHANGE_PASSWORD=your_password_optional
EXCHANGE_API_DOMAIN=api1.binance.com
EXCHANGE_PROXY=http://127.0.0.1:7890
EXCHANGE_SANDBOX=false
```

## 🧪 测试网与主网
开发与演示默认使用 Nile 测试网：
- TronGrid Nile: https://nile.trongrid.io （无需 API key，QPS 50/单 IP）
- TronScan Nile: https://nileapi.tronscan.org/api （无需 API key，QPS 50/单 IP）
- 浏览器: https://nile.tronscan.org/
- 水龙头: https://nileex.io/join/getJoinPage

如需切回主网，在环境变量里覆盖：
```bash
export TRONGRID_BASE=https://api.trongrid.io
export TRONSCAN_BASE=https://apilist.tronscanapi.com/api
```

## 🔧 配置 (config.toml / 环境变量)
```
PORT
TRONSCAN_BASE      (默认 https://nileapi.tronscan.org/api)
TRONGRID_BASE      (默认 https://nile.trongrid.io)
TRONSCAN_API_KEY   (TRC20/labels 备份查询)
TRONGRID_API_KEY | TRON_PRO_API_KEY
TRON_USDT_CONTRACT (默认 TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t)
COINGECKO_BASE     (默认 https://api.coingecko.com/api/v3)
REQUEST_TIMEOUT_MS
LOG_LEVEL, LOG_FILE
AI_API_BASE, AI_API_KEY, AI_MODEL, AI_PROVIDER  # 可选，启用 LLM 编排
SAFETY_ENABLE      (true/false，控制 _human_notes)
TELEGRAM_BOT_TOKEN (可选)
TELEGRAM_CHAT_ID   (可选)
TELEGRAM_SUBSCRIBERS_PATH (可选，默认 logs/telegram_subscribers.json)
TELEGRAM_ALLOW_ALL (可选，true 则允许所有 chat_id 访问 bot)
TELEGRAM_AUTH_BOT_TOKEN (可选，验证码使用的单独 bot token)
AUDIT_LOG_DIR      (可选，默认 logs/transactions)
MARKET_DATA_BASE   (可选，默认 https://api.binance.com)
EXCHANGE_ID        (可选)
EXCHANGE_API_KEY   (可选)
EXCHANGE_SECRET    (可选)
EXCHANGE_PASSWORD  (可选)
EXCHANGE_API_DOMAIN (可选，binance 域名替换，如 api1.binance.com)
EXCHANGE_PROXY      (可选，HTTP/SOCKS 代理，如 http://127.0.0.1:7890 或 socks5://127.0.0.1:1080)
RISK_RULES_PATH     (可选，默认 risk_rules.json)
ONCHAIN_RULES_PATH  (可选，默认 onchain_rules.json)
ONCHAIN_STATE_PATH  (可选，默认 logs/onchain_state.json)
```

风险规则配置：
`risk_rules.json` 可自定义仓位预警与开仓辅助阈值；如需自定义路径，可设置 `RISK_RULES_PATH`。
新增仓位/订单监控项（positions）：
- `max_unrealized_loss_pct`：单仓浮亏阈值（例如 -0.05 表示 -5%）
- `max_leverage`：单仓杠杆上限
- `max_position_notional_ratio`：单仓名义价值占总资产比例上限
- `max_open_orders`：未成交订单数量上限

链上监控配置：
`onchain_rules.json` 定义监控地址/代币与阈值（务必填写真实地址）；如需自定义路径，可设置 `ONCHAIN_RULES_PATH`。
EVM 监控可在规则中配置 `chain: "EVM"` 并提供 `rpc_url`（或写入 `evm_rpcs` 映射）。

定期监控示例（自动推送到 Telegram）：
```bash
# 链上资产监控（读取 onchain_rules.json）
python3 monitor.py --mode onchain --interval 60 --notify --broadcast

# 交易所仓位预警（读取 risk_rules.json）
python3 monitor.py --mode position --exchange-id binance --interval 60 --notify --broadcast

# 全部监控（可分别指定规则文件）
python3 monitor.py --mode all --exchange-id binance --interval 60 --notify --broadcast \
  --onchain-rules onchain_rules.json --risk-rules risk_rules.json

# 开启审计日志
python3 monitor.py --mode onchain --interval 60 --notify --broadcast --audit
```

`onchain_rules.json` 示例：
```json
{
  "interval_sec": 60,
  "notify_on": ["increase", "decrease"],
  "min_change_default": 0.01,
  "state_path": "logs/onchain_state.json",
  "evm_rpcs": {
    "ETH": "https://your-ethereum-rpc"
  },
  "addresses": [
    {
      "address": "YOUR_TRON_ADDRESS",
      "tokens": ["TRX", "USDT"],
      "thresholds": { "TRX": 5, "USDT": 1 }
    },
    {
      "label": "evm-wallet",
      "chain": "EVM",
      "network": "ETH",
      "rpc_url": "https://your-ethereum-rpc",
      "address": "0xYourEvmAddress",
      "tokens": [
        "ETH",
        { "symbol": "USDT", "type": "ERC20", "contract": "0xYourTokenContract", "decimals": 6 }
      ],
      "thresholds": { "ETH": 0.05, "USDT": 10 }
    }
  ]
}
```
👉 建议把真实 key 放 `.env`（已在 `.gitignore`），示例见 `.env.example`。

**私钥配置（本地签名专用）**
1. 复制示例文件：
```bash
cp .env.private.example .env.private
```
2. 填写私钥（十六进制，不带 `0x`）：
```
TRON_PRIVATE_KEY=your_private_key_hex
```
3. 使用本地签名工具：
```bash
python3 -c "from tron_mcp.extensions.local_signer import sign_transaction; print(sign_transaction({'txID':'...','raw_data_hex':'...'}))"
```

`.env.private` 已加入 `.gitignore`，不会被提交。

## 📄 提交材料与文档
- 部署文档: [../DEPLOYMENT.md](../DEPLOYMENT.md)
- API 文档: [../API.md](../API.md)

## ✅ 开源合规与创新
- 允许使用开源库/模板，但需在代码注释或文档中标注来源。
- 核心业务逻辑需原创或有明显改造，避免整项目复制粘贴。

## 📂 目录速览
- `run.py` — FastMCP 入口。
- `tron_mcp/tools.py` — 工具实现与校验。
- `tron_mcp/tron_api.py` — TRONSCAN/TRONGRID HTTP helper（自动附加 API key）。
- `tron_mcp/safety.py` — `_human_notes` 注释器。
- `tron_mcp/settings.py` — 读取 config.toml + env。
- `tron_mcp/ai/client.py` — LLM 客户端（OpenAI/DeepSeek/Anthropic 等）。
- `tron_mcp/extensions/agent_pipeline.py` — 意图解析 → 确认 → 构建 → 签名请求 → 广播。
- `tron_mcp/extensions/trc20_assistant.py` — TRC20 未签名转账构建。
- `agents/agent_runner.py` — 彩色 CLI agent（推荐）。
- `agents/ai_llm_tool_call.py` — 极简 LLM demo。
- `agents/tui_app.py` — Textual TUI（可选）。

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
审计日志结构说明见 `AUDIT_SCHEMA.md`。
