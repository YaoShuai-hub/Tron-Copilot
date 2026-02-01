"""Robust AI client for mainstream chat APIs with tool schema support.

Supported providers (settings.ai_provider):
    - openai (default, OpenAI-compatible /v1/chat/completions)
    - azure-openai (deployment name in settings.ai_model)
    - anthropic (/v1/messages)
    - custom (POST to ai_api_base/chat/completions)

Features:
    * Stdlib-only HTTP.
    * Exponential backoff on 429/5xx and network errors.
    * Respects settings.request_timeout.
    * AI concerns remain separate from MCP runtime.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from tron_mcp import settings
from tron_mcp.utils.errors import UpstreamError, ValidationError

log = logging.getLogger(__name__)

MAX_RETRIES = 3
BACKOFF_BASE = 0.8


def _require_config() -> None:
    """Ensure mandatory AI config is present."""
    missing = []
    if not settings.SETTINGS.ai_api_base:
        missing.append("ai_api_base")
    if not settings.SETTINGS.ai_model:
        missing.append("ai_model")
    if missing:
        raise ValidationError(f"AI config missing: {', '.join(missing)}")


def _headers() -> Dict[str, str]:
    hdrs = {"Content-Type": "application/json"}
    if settings.SETTINGS.ai_api_key:
        hdrs["Authorization"] = f"Bearer {settings.SETTINGS.ai_api_key}"
    return hdrs


def _build_url() -> str:
    base = settings.SETTINGS.ai_api_base.rstrip("/")
    provider = settings.SETTINGS.ai_provider.lower()
    if provider == "deepseek":
        return f"{base}/v1/chat/completions"
    if provider in {"openai", "custom"}:
        return f"{base}/chat/completions"
    if provider == "azure-openai":
        return (
            f"{base}/openai/deployments/{settings.SETTINGS.ai_model}"
            "/chat/completions?api-version=2024-02-15-preview"
        )
    if provider == "anthropic":
        return f"{base}/v1/messages"
    return f"{base}/chat/completions"


def _payload(messages: List[Dict[str, str]], tools_schema: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    def _format_tools_for_openai(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Ensure tools match OpenAI/DeepSeek format (type=function)."""
        formatted: List[Dict[str, Any]] = []
        for tool in tools:
            # Pass through if already in expected shape
            if "type" in tool and "function" in tool:
                formatted.append(tool)
                continue
            formatted.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.get("name"),
                        "description": tool.get("description", ""),
                        "parameters": tool.get("inputSchema", {}) or {},
                    },
                }
            )
        return formatted

    def _format_tools_for_anthropic(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Anthropic expects input_schema instead of parameters/type."""
        formatted: List[Dict[str, Any]] = []
        for tool in tools:
            formatted.append(
                {
                    "name": tool.get("name"),
                    "description": tool.get("description", ""),
                    "input_schema": tool.get("inputSchema", {}) or {},
                }
            )
        return formatted

    provider = settings.SETTINGS.ai_provider.lower()
    if provider == "anthropic":
        return {
            "model": settings.SETTINGS.ai_model,
            "messages": messages,
            "tools": _format_tools_for_anthropic(tools_schema) if tools_schema else [],
            "max_tokens": 512,
        }
    payload: Dict[str, Any] = {"model": settings.SETTINGS.ai_model, "messages": messages}
    if tools_schema:
        payload["tools"] = _format_tools_for_openai(tools_schema)
        payload["tool_choice"] = "auto"
    return payload


def _request(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    url = _build_url()
    req = urllib.request.Request(url=url, data=data, headers=_headers(), method="POST")
    last_err: Exception | None = None
    toggled = False  # track deepseek path toggle to avoid infinite loop
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=settings.SETTINGS.request_timeout) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                text = resp.read().decode(charset, errors="replace")
                return json.loads(text)
        except urllib.error.HTTPError as err:
            body = err.read().decode("utf-8", errors="replace") if err.fp else ""

            # DeepSeek 405 兼容：在 /chat/completions 与 /v1/chat/completions 之间切换重试一次
            if err.code == 405 and settings.SETTINGS.ai_provider.lower() == "deepseek":
                if not toggled:
                    if url.endswith("/chat/completions"):
                        alt_url = url.replace("/chat/completions", "/v1/chat/completions")
                    elif url.endswith("/v1/chat/completions"):
                        alt_url = url.replace("/v1/chat/completions", "/chat/completions")
                    else:
                        alt_url = url
                    if alt_url != url:
                        log.info("DeepSeek 405 received, retrying with %s", alt_url)
                        url = alt_url
                        req = urllib.request.Request(url=alt_url, data=data, headers=_headers(), method="POST")
                        toggled = True
                        last_err = None
                        continue

            # Try to surface a concise, human-friendly error message from the provider response.
            summary = None
            try:
                data = json.loads(body)
                # Common layouts: {"error":{"message":...}}, {"message":...}, {"msg":...}
                summary = (
                    data.get("error", {}).get("message")
                    if isinstance(data.get("error"), dict)
                    else data.get("error")
                ) or data.get("message") or data.get("msg")
            except Exception:
                pass

            if summary:
                summary = str(summary)
            else:
                summary = body[:400] if body else "No error body returned"

            last_err = UpstreamError(
                f"AI API HTTP {err.code}: {summary}",
                status=err.code,
                body=body,
            )

            if err.code in {429, 500, 502, 503, 504} and attempt < MAX_RETRIES:
                time.sleep(BACKOFF_BASE * (2 ** (attempt - 1)))
                continue
            raise last_err
        except urllib.error.URLError as err:
            last_err = UpstreamError(f"AI API network error: {err.reason}")
            if attempt < MAX_RETRIES:
                time.sleep(BACKOFF_BASE * (2 ** (attempt - 1)))
                continue
            raise last_err
        except Exception as err:  # noqa: BLE001
            last_err = err
            if attempt < MAX_RETRIES:
                time.sleep(BACKOFF_BASE * (2 ** (attempt - 1)))
                continue
            raise
    if last_err:
        raise last_err
    raise UpstreamError("AI provider returned no response after retries")


def call_chat(messages: List[Dict[str, str]], tools_schema: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Call the configured chat provider with optional tool schema.

    Args:
        messages: list of {role, content} dicts.
        tools_schema: optional MCP tool definitions for function/tool calling.
    Returns:
        Parsed JSON response.
    Raises:
        ValidationError if configuration is incomplete.
        UpstreamError on HTTP/network errors.
    """
    _require_config()
    payload = _payload(messages, tools_schema)
    return _request(payload)
