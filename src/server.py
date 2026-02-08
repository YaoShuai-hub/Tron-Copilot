"""FastAPI backend for the Copilot frontend.

Endpoints:
- POST /chat: LLM chat with tool-calling (non-streaming response body).
- POST /api/analyze-error: structured error analysis used by TransactionCard.
- POST /api/rent-energy: energy rental simulation endpoint (imported router).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel

from config import Config

from tron_mcp import tools as tron_tools

try:
    from openai import AsyncOpenAI
except Exception:  # pragma: no cover
    AsyncOpenAI = None  # type: ignore[assignment]


SYSTEM_TOOL_POLICY = (
    "If the available tools cannot solve the task, prioritize creating a custom tool by "
    "calling custom_tools_write with a Python module (define TOOL_DEFINITIONS and call_tool), "
    "then call custom_tools_reload, and then use the new tool. "
    "If a tool with the same name already exists, call it first. "
    "If the tool is buggy, iteratively rewrite it and reload."
)


class ChatRequest(BaseModel):
    message: str
    wallet_address: Optional[str] = None
    network: str = "nile"


class AnalyzeErrorRequest(BaseModel):
    error_message: str
    error_context: Optional[str] = None
    transaction_details: Optional[Dict[str, Any]] = None


CONVERSATION_HISTORY: List[Dict[str, Any]] = []


def _get_ai_client():
    if not Config.AI_API_KEY or not AsyncOpenAI:
        return None
    kwargs: Dict[str, Any] = {"api_key": Config.AI_API_KEY}
    if Config.AI_API_BASE:
        kwargs["base_url"] = Config.AI_API_BASE
    return AsyncOpenAI(**kwargs)


ai_client = _get_ai_client()


def get_llm_tools() -> List[Dict[str, Any]]:
    """Convert tron_mcp tool definitions to OpenAI tool schema."""
    items = tron_tools.list_tools().get("tools", [])
    out: List[Dict[str, Any]] = []
    for tool in items:
        name = tool.get("name")
        if not name:
            continue
        out.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.get("description") or "",
                    "parameters": tool.get("inputSchema") or {"type": "object", "properties": {}},
                },
            }
        )
    return out


async def execute_tool(name: str, args: Dict[str, Any]) -> str:
    """Run a tron_mcp tool safely from FastAPI's async loop."""
    result = await asyncio.to_thread(tron_tools.call_tool, name, args)
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception:
        return str(result)


def _fallback_response(message: str) -> str:
    return (
        "⚠️ 当前未配置 AI_API_KEY，智能对话不可用。\n\n"
        f"你的消息：{message}\n\n"
        "你可以在 `config.toml` 或环境变量中设置 `AI_API_KEY` 后重试。"
    )


app = FastAPI(title="TRON Copilot API")
app.extra["ai_provider"] = Config.AI_PROVIDER
app.extra["ai_model"] = Config.AI_MODEL

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Optional API router(s)
try:
    from api.rent_energy import router as rent_energy_router

    app.include_router(rent_energy_router, prefix="/api")
except Exception:
    # If dependencies for this router are missing, don't fail app import.
    pass


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"ok": True}


@app.post("/api/analyze-error")
async def analyze_error(req: AnalyzeErrorRequest):
    payload = await asyncio.to_thread(
        tron_tools.call_tool,
        "analyze_error",
        {"error_message": req.error_message},
    )
    if isinstance(payload, str):
        return JSONResponse({"analysis": payload, "possible_causes": [], "suggestions": []})
    return JSONResponse(payload)


@app.post("/chat")
async def chat(req: ChatRequest) -> PlainTextResponse:
    if not ai_client:
        return PlainTextResponse(_fallback_response(req.message))

    system_prompt = f"""{SYSTEM_TOOL_POLICY}

你是 TRON Copilot，一个精通 TRON 区块链的中文助手。
用户钱包地址：{req.wallet_address or "未连接"}
网络：{req.network}

规则：
1) 用户说中文你就用中文回复
2) URL 必须使用 Markdown 链接格式：[标题](URL)
3) 如果工具返回了 \"Skill 链执行结果\" 区块，必须原样输出，不要省略。
4) 对未知需求，优先使用 custom_tools_write/custom_tools_reload 创建并使用自定义工具。
"""

    messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    messages.extend(CONVERSATION_HISTORY[-10:])
    messages.append({"role": "user", "content": req.message})

    all_tools = get_llm_tools()

    try:
        # First model call (may request tool calls)
        response = await ai_client.chat.completions.create(
            model=Config.AI_MODEL,
            messages=messages,
            tools=all_tools,
            tool_choice="auto",
            stream=False,
        )
        choice = response.choices[0].message
        tool_calls = choice.tool_calls or []
        content = choice.content or ""

        if not tool_calls:
            CONVERSATION_HISTORY.append({"role": "user", "content": req.message})
            CONVERSATION_HISTORY.append({"role": "assistant", "content": content})
            return PlainTextResponse(content)

        # Append assistant tool call message
        assistant_msg = {
            "role": "assistant",
            "content": content if content else None,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name or "", "arguments": tc.function.arguments or "{}"},
                }
                for tc in tool_calls
            ],
        }
        messages.append(assistant_msg)

        output_chunks: List[str] = []
        tool_json_blocks: List[str] = []

        # Execute requested tools; keep transfer visualization as part of final output.
        output_chunks.append("\n\n---\n\n")
        output_chunks.append("🔧 **正在执行 Skills**：\n\n")

        import re

        for tc in tool_calls:
            fn_name = tc.function.name or ""
            fn_args_str = tc.function.arguments or "{}"
            try:
                fn_args = json.loads(fn_args_str)
            except json.JSONDecodeError:
                fn_args = {}

            result_str = ""
            if fn_name == "transfer_tokens":
                to_address = fn_args.get("to_address", "")
                token = fn_args.get("token", "TRX")
                amount = fn_args.get("amount", 0)

                output_chunks.append("📇 **Step 1/5 - 地址簿查询**\n")
                step_result = await execute_tool("record_transfer", {"to_address": to_address})
                output_chunks.append(f"{step_result}\n\n")

                output_chunks.append("🚨 **Step 2/5 - 恶意地址检测**\n")
                step_result = await execute_tool(
                    "check_malicious",
                    {"address": to_address, "network": req.network},
                )
                output_chunks.append(f"{step_result}\n\n")

                output_chunks.append("🔒 **Step 3/5 - 安全风险评估**\n")
                step_result = await execute_tool("check_address_security", {"address": to_address})
                output_chunks.append(f"{step_result}\n\n")

                output_chunks.append("⚡ **Step 4/5 - 能量计算**\n")
                step_result = await execute_tool("calculate_energy", {"token": token, "network": req.network})
                output_chunks.append(f"{step_result}\n\n")

                output_chunks.append("🔨 **Step 5/5 - 构建交易**\n")
                result_str = await execute_tool(
                    "build_transfer",
                    {
                        "from_address": req.wallet_address,
                        "to_address": to_address,
                        "token": token,
                        "amount": amount,
                        "memo": fn_args.get("memo", ""),
                        "network": req.network,
                    },
                )
                output_chunks.append(f"{result_str}\n\n")
                output_chunks.append("---\n\n")
            else:
                # Generic tool execution
                result_str = await execute_tool(fn_name, fn_args)
                if result_str:
                    output_chunks.append(f"• `{fn_name}`\n{result_str}\n\n")

            # Extract JSON blocks for TransactionCard
            json_pattern = r'<<<JSON\\s*(.*?)\\s*JSON>>>'
            matches = re.findall(json_pattern, result_str or "", re.DOTALL)
            for json_content in matches:
                tool_json_blocks.append(f"<<<JSON\n{json_content}\nJSON>>>")

            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result_str or ""})

        # Second model call to produce final answer after tools
        second = await ai_client.chat.completions.create(
            model=Config.AI_MODEL,
            messages=messages,
            stream=False,
        )
        final_content = second.choices[0].message.content or ""

        # Persist short history
        CONVERSATION_HISTORY.append({"role": "user", "content": req.message})
        CONVERSATION_HISTORY.append(assistant_msg)
        for msg in messages:
            if msg.get("role") == "tool":
                CONVERSATION_HISTORY.append(msg)
        CONVERSATION_HISTORY.append({"role": "assistant", "content": final_content})

        output = "".join(output_chunks) + final_content
        if tool_json_blocks:
            output += "\n\n" + "\n\n".join(tool_json_blocks)
        return PlainTextResponse(output)

    except Exception as e:  # noqa: BLE001
        return PlainTextResponse(f"❌ AI Error: {str(e)}")

