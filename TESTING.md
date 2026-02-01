# ✅ Trident MCP — 测试手册

目标：快速确认依赖、配置与 6 个工具都能正常工作，并展示给他人演示用。假设已 `source .venv/bin/activate`。

## 0) 安装
```bash
pip3 install -r requirements.txt
# 若要跑 Textual TUI：
# pip3 install textual
```

## 1) 配置检查
- `config.toml` 或环境变量里至少填：`TRONGRID_API_KEY`（推荐）、`TRONSCAN_API_KEY`。  
- 可选 LLM：`AI_API_BASE`, `AI_API_KEY`, `AI_MODEL`, `AI_PROVIDER`。  
- 敏感 key 放 `.env`（已忽略）；可参考 `.env.example`。

## 2) 单行 smoke（无需起服务器）
```bash
python tool_smoke.py --address TPwjKc2nfSb6Zxk4sZDSZu6f9QaK3xktAP
# 可加 --txid <hash> 或 --verbose
```
期待输出：network params + USDT 余额；若 400/401 多为 API key 问题。

## 3) 直接 python -c 快测新工具
```bash
python3 -c "from tron_mcp import tools; print(tools.get_recent_transactions('THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF', limit=5))"
python3 -c "from tron_mcp import tools; print(tools.get_trc20_transfers('THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF', limit=5))"
python3 -c "from tron_mcp import tools; print(tools.get_address_labels('THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF'))"
```
若出现 400/401，检查 key 和 TRONSCAN 控制台白名单。

## 4) MCP stdio 服务
```bash
python3 run.py
```
用 MCP 客户端验证：
1. `list_tools` 应列出 6 个工具。  
2. `call_tool get_network_params {}`  
3. `call_tool get_usdt_balance {address:"T..."}`  
4. `call_tool get_tx_status {txid:"64hex"}`  
5. `call_tool get_recent_transactions {address:"T...",limit:5}`  
6. `call_tool get_trc20_transfers {address:"T...",limit:5}`  
7. `call_tool get_address_labels {address:"T..."}`  

## 5) 彩色 CLI Agent（推荐演示）
```bash
python3 -m agents.agent_runner --prompt "Show me TRON energy and bandwidth fees."
# 交互：
python3 -m agents.agent_runner
# 调试模式（打印 LLM 请求/响应）：
python3 -m agents.agent_runner --debug --prompt "Show the latest 5 TRC20 transfers involving address THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF."
```
应看到 Trace 面板列出工具调用与返回结果，最终消息为自然语言总结。

## 6) AI LLM 桥接（可选）
```bash
python3 -m agents.ai_llm_tool_call
```
未配置 AI 会报校验错误；配置正确会打印 LLM 原始 JSON。

## 7) Textual TUI（可选）
```bash
python3 -m agents.tui_app
```

## 8) 示例对话（agent_runner 可直接粘贴）
- Q1: Show me the current TRON network energy fee and bandwidth fee.  
- Q2: Check the USDT balance of TPwjKc2nfSb6Zxk4sZDSZu6f9QaK3xktAP.  
- Q3: Is transaction 17c46bf2625aaf21b28a0c54783715d63380ccdb3d1134c8365e2628a5e2f6c4 confirmed?  
- Q4: List the last 5 transactions for address THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF.  
- Q5: Show the latest 5 TRC20 transfers involving address THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF.  
- Q6: What labels or flags does TRON address THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF have?  

## 9) 常见问题
- 400/401：API key 无效或 TRONSCAN 控制台限制来源；确认填写并解锁白名单。  
- 看不到 `_human_notes`：确认 `SAFETY_ENABLE` 未被设成 false。  
- LLM 405/超时：用 `--debug` 查看往返；失败时工具结果仍会 fallback 输出。  
