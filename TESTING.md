# Trident MCP — Quick Test Guide

Use this to sanity‑check before演示/提交。假设已 `source .venv/bin/activate`。

## 0) Install deps
```bash
pip install -r requirements.txt
# Textual (only if你要跑 TUI)
# pip install textual
```

## 1) Config sanity
- 确认 `config.toml` 或环境变量里已填：`TRONGRID_API_KEY`（推荐）、`TRONSCAN_API_KEY`、`TRONSCAN_BASE`、`TRONGRID_BASE`。
- 可选 AI：`AI_API_BASE`, `AI_API_KEY`, `AI_MODEL`, `AI_PROVIDER`。
- Safety：默认开启；设 `SAFETY_ENABLE=false` 可关。

## 2) Tool smoke (无需起服务器)
```bash
python tool_smoke.py --address TPwjKc2nfSb6Zxk4sZDSZu6f9QaK3xktAP
# 可加 --txid <hash> 或 --verbose
```
期待输出 network params + USDT 余额，若无网络/Key 会报 UpstreamError。

## 3) 直接 python -c 快测新工具
```bash
python -c "from tron_mcp import tools; print(tools.get_recent_transactions('THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF', limit=5))"
python -c "from tron_mcp import tools; print(tools.get_trc20_transfers('THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF', limit=5))"
python -c "from tron_mcp import tools; print(tools.get_address_labels('THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF'))"
```
若 400/401，检查 API key 填写与权限设置。

## 4) MCP stdio 服务
```bash
python run.py
```
用任意 MCP 客户端连（stdio）。验证：
1. `list_tools` 列出六个工具。
2. `call_tool get_network_params {}` 返回费用字段。
3. `call_tool get_usdt_balance {address: <T...>}` 返回余额（含 `_human_notes` 取决于 safety）。
4. `call_tool get_tx_status {txid: <64hex>}` 返回状态/收据。
5. `call_tool get_recent_transactions {address: <T...>, limit: 5}` 返回最近交易。
6. `call_tool get_trc20_transfers {address: <T...>, limit: 5}` 返回最近 TRC20 转账。
7. `call_tool get_address_labels {address: <T...>}` 返回标签/标记。

## 5) 彩色 CLI agent（推荐演示）
```bash
python -m agents.agent_runner --prompt "Show me TRON energy and bandwidth fees."
# 交互模式：python -m agents.agent_runner
# 调试模式（打印 LLM 往返）：python -m agents.agent_runner --debug
```
应看到：
- 输入面板
- Trace 面板显示 LLM 回复与工具调用、结果
- Final message 单独显示

## 6) AI LLM 桥接（可选）
```bash
python -m agents.ai_llm_tool_call
```
未配置 AI 会抛 ValidationError；配置正确则打印 LLM 原始 JSON。

## 7) Textual TUI（可选，不想用可跳过）
```bash
python -m agents.tui_app
```

## 常见问题
- `ModuleNotFoundError: fastmcp`：确保在 `.venv` 内且已 `pip install -r requirements.txt`。
- HTTP 4xx/5xx：多为 API Key 无效或请求超时；检查 `TRONGRID_API_KEY` 与网络。
- 看不到 `_human_notes`：确认 `SAFETY_ENABLE` 未被环境关闭。***

## 8) 示例对话（agent_runner 可直接粘贴）
- Q1: Show me the current TRON network energy fee and bandwidth fee.
- Q2: Check the USDT balance of TPwjKc2nfSb6Zxk4sZDSZu6f9QaK3xktAP.
- Q3: Is transaction 17c46bf2625aaf21b28a0c54783715d63380ccdb3d1134c8365e2f6c4 confirmed?
- Q4: List the last 5 transactions for address THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF.
- Q5: Show the latest 5 TRC20 transfers involving address THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF.
- Q6: What labels or flags does TRON address THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF have?
