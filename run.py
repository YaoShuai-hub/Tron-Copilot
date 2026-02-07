"""FastMCP entry point for Trident MCP.

Usage:
    pip install fastmcp
    python3 run.py

How it works:
    - Registers TRON tools with FastMCP and serves via MCP stdio.
    - Reads configuration from settings (config.toml + env overrides).
    - Logging is initialized before the server loop starts.

Exposed tools (all return JSON-serializable dicts):
    get_usdt_balance(address: str) -> dict
        Input: TRON base58 address starting with 'T'.
        Return: {address, contract, balance:{raw,human,decimals}, source, apiUrl, updated}
        Example: mcp.call_tool("get_usdt_balance", {"address": "TPwjKc2nfSb6Zxk4sZDSZu6f9QaK3xktAP"})

    get_network_params() -> dict
        Input: none.
        Return: {energyFeeSun, bandwidthFeeSun, createAccountFeeSun, memoFeePerByteSun, notes, raw}
        Example: mcp.call_tool("get_network_params", {})

    get_tx_status(txid: str) -> dict
        Input: 64-character hex transaction id.
        Return: {txid, status, blockNumber, blockTime, feeSun, energyUsage, rawMeta, rawReceipt}
        Example: mcp.call_tool("get_tx_status", {"txid": "<tx_hash>"})

    get_token_balance(address: str, token: str) -> dict
        Input: TRON base58 address + token symbol/contract (TRX/USDT or contract address).
        Return: {address, token{symbol,contract,decimals,name,matchedBy}, balance{raw,human,decimals}, source, apiUrl, updated}
        Example: mcp.call_tool("get_token_balance", {"address": "T...", "token": "USDT"})

    get_total_value(address: str, currency: str = "usd") -> dict
        Input: TRON base58 address + currency (usd/cny).
        Return: {address, currency, totalValue, items[], missingPrices, pricingSource, apiUrl, updated}
        Example: mcp.call_tool("get_total_value", {"address": "T...", "currency": "cny"})
"""

import sys

from fastmcp import FastMCP

from tron_mcp import safety, settings, tools
from tron_mcp.extensions import tx_assistant, trc20_assistant, agent_pipeline, local_signer
from tron_mcp.modules import chain_ops, funds_flow, notify_telegram, audit_log, market_data, exchange_adapter
from tron_mcp.utils.logging_setup import setup_logging


mcp = FastMCP(
    name="Trident MCP",
    version="0.3.0",
)


@mcp.tool(name="get_usdt_balance", description="Read-only: get TRC20 USDT balance for a TRON address (TRONSCAN).")
def tool_get_usdt_balance(address: str) -> dict:
    """USDT balance breakdown for a TRON address.

    Args:
        address: TRON Base58 address starting with 'T'.
    Returns:
        Dict with fields:
            address, contract, balance {raw, human, decimals},
            source, apiUrl, updated (timestamp if available).
    Example:
        mcp.call_tool("get_usdt_balance", {"address": "TPwjKc2nfSb6Zxk4sZDSZu6f9QaK3xktAP"})
    """
    return safety.enrich(tools.get_usdt_balance(address))


@mcp.tool(name="get_trx_balance", description="Read-only: get TRX balance for a TRON address (TRONGRID).")
def tool_get_trx_balance(address: str) -> dict:
    """TRX balance for a TRON address.

    Args:
        address: TRON Base58 address starting with 'T'.
    Returns:
        Dict with address, balance {raw, human, decimals}, source, apiUrl, updated, raw.
    """
    return safety.enrich(tools.get_trx_balance(address))

@mcp.tool(name="get_network_params", description="Read-only: get chain fee parameters (energy/bandwidth/create account).")
def tool_get_network_params() -> dict:
    """Current TRON chain parameters.

    Args:
        None.
    Returns:
        Dict with energyFeeSun, bandwidthFeeSun, createAccountFeeSun,
        memoFeePerByteSun, notes, raw (full API payload).
    Example:
        mcp.call_tool("get_network_params", {})
    """
    return safety.enrich(tools.get_network_params())


@mcp.tool(name="get_tx_status", description="Read-only: get TRON tx confirmation + receipt summary by txid (hex).")
def tool_get_tx_status(txid: str) -> dict:
    """Transaction confirmation status and receipt summary.

    Args:
        txid: 64-character hexadecimal transaction id.
    Returns:
        Dict with txid, status, blockNumber, blockTime, feeSun,
        energyUsage, rawMeta, rawReceipt.
    Example:
        mcp.call_tool("get_tx_status", {"txid": "<tx_hash>"})
    """
    return safety.enrich(tools.get_tx_status(txid))


@mcp.tool(name="get_recent_transactions", description="Read-only: list recent TRX transactions for an address (TRONGRID→TRONSCAN).")
def tool_get_recent_transactions(address: str, limit: int = 20) -> dict:
    """Recent transactions for a TRON address (concise list).

    Args:
        address: TRON Base58 address starting with 'T'.
        limit: Max items to return (1-50).
    Returns:
        Dict with address, count, items[{txid,timestamp,ret,contractType,direction,from,to}], source.
        Source is TRONGRID if available, otherwise TRONSCAN.
    Example:
        mcp.call_tool("get_recent_transactions", {"address": "THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF", "limit": 5})
    """
    return safety.enrich(tools.get_recent_transactions(address, limit))


@mcp.tool(name="get_trc20_transfers", description="Read-only: list recent TRC20 transfers for an address (TRONGRID→TRONSCAN).")
def tool_get_trc20_transfers(address: str, limit: int = 20) -> dict:
    """Recent TRC20 transfers related to an address.

    Args:
        address: TRON Base58 address starting with 'T'.
        limit: Max items to return (1-50).
    Returns:
        Dict with address, count, items[{txid,timestamp,token{symbol,contract,decimals},
        amountRaw, amountHuman, from, to, direction}], source (TRONGRID or TRONSCAN).
    Example:
        mcp.call_tool("get_trc20_transfers", {"address": "THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF", "limit": 5})
    """
    return safety.enrich(tools.get_trc20_transfers(address, limit))


@mcp.tool(name="get_address_labels", description="Read-only: lookup address labels/tags/flags (TRONSCAN).")
def tool_get_address_labels(address: str) -> dict:
    """Address labels/flags from TRONSCAN account payload.

    Args:
        address: TRON Base58 address starting with 'T'.
    Returns:
        Dict with address, name, tags, isContract, isShielded, source, raw (original payload).
    Example:
        mcp.call_tool("get_address_labels", {"address": "THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF"})
    """
    return safety.enrich(tools.get_address_labels(address))


tx_assistant.register_mcp_tools(mcp)
trc20_assistant.register_mcp_tools(mcp)
agent_pipeline.register_mcp_tools(mcp)
local_signer.register_mcp_tools(mcp)
chain_ops.register_mcp_tools(mcp)
funds_flow.register_mcp_tools(mcp)
notify_telegram.register_mcp_tools(mcp)
audit_log.register_mcp_tools(mcp)
market_data.register_mcp_tools(mcp)
exchange_adapter.register_mcp_tools(mcp)


@mcp.tool(name="get_token_balance", description="Read-only: get TRX or TRC20 balance by symbol/contract (TRONSCAN).")
def tool_get_token_balance(address: str, token: str) -> dict:
    """Token balance for a TRON address.

    Args:
        address: TRON Base58 address starting with 'T'.
        token: Token symbol (e.g. TRX/USDT) or TRC20 contract address.
    Returns:
        Dict with address, token{symbol,contract,decimals,name,matchedBy},
        balance{raw,human,decimals}, source, apiUrl, updated.
    Example:
        mcp.call_tool("get_token_balance", {"address": "TPw...", "token": "TRX"})
    """
    return safety.enrich(tools.get_token_balance(address, token))


@mcp.tool(name="get_total_value", description="Read-only: compute total value (TRX+TRC20) in usd/cny with pricing.")
def tool_get_total_value(address: str, currency: str = "usd") -> dict:
    """Total portfolio value in USD/CNY using CoinGecko pricing.

    Args:
        address: TRON Base58 address starting with 'T'.
        currency: "usd" or "cny".
    Returns:
        Dict with address, currency, totalValue, items, missingPrices, pricingSource, apiUrl.
    Example:
        mcp.call_tool("get_total_value", {"address": "TPw...", "currency": "usd"})
    """
    return safety.enrich(tools.get_total_value(address, currency))


def main() -> int:
    """Initialize logging and start FastMCP stdio server.

    Returns:
        int: 0 on normal exit.
    """
    setup_logging(level=settings.SETTINGS.log_level, logfile=settings.SETTINGS.log_file)
    try:
        mcp.run()
    except KeyboardInterrupt:
        # Graceful shutdown instead of noisy traceback
        import logging

        logging.getLogger(__name__).info("Shutting down (KeyboardInterrupt)")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
