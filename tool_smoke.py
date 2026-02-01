"""Smoke test for Trident MCP tools with concise output.

Usage examples:
    python tool_smoke.py --address TPwjKc2nfSb6Zxk4sZDSZu6f9QaK3xktAP
    python tool_smoke.py --address <addr> --txid <txhash> --verbose

What it does:
    - Calls get_network_params, get_usdt_balance (address required),
      and optionally get_tx_status if txid provided.
    - Prints concise summaries (avoids dumping large raw payloads).
    - Uses safety.enrich for human notes unless --no-safety is set.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict

# Allow running as a standalone script
sys.path.insert(0, ".")

from tron_mcp import safety, settings, tools  # noqa: E402


def summarize_network(params: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "energyFeeSun": params.get("energyFeeSun"),
        "bandwidthFeeSun": params.get("bandwidthFeeSun"),
        "createAccountFeeSun": params.get("createAccountFeeSun"),
        "memoFeePerByteSun": params.get("memoFeePerByteSun"),
        "notes": params.get("notes"),
    }


def summarize_usdt(balance: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "address": balance.get("address"),
        "contract": balance.get("contract"),
        "human": balance.get("balance", {}).get("human"),
        "raw": balance.get("balance", {}).get("raw"),
        "decimals": balance.get("balance", {}).get("decimals"),
        "updated": balance.get("updated"),
    }


def summarize_tx(tx: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "txid": tx.get("txid"),
        "status": tx.get("status"),
        "blockNumber": tx.get("blockNumber"),
        "blockTime": tx.get("blockTime"),
        "feeSun": tx.get("feeSun"),
        "energyUsage": tx.get("energyUsage"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test MCP tools (concise output).")
    parser.add_argument("--address", help="TRON address for USDT balance", required=True)
    parser.add_argument("--txid", help="TRON txid to query status", default=None)
    parser.add_argument("--verbose", action="store_true", help="Print full JSON responses")
    parser.add_argument("--no-safety", action="store_true", help="Skip safety enrichment")
    args = parser.parse_args()

    enrich = (lambda x: x) if args.no_safety else safety.enrich

    print("Safety enabled:", settings.SETTINGS.safety_enable and not args.no_safety)

    # Network params
    net_raw = tools.get_network_params()
    net_out = net_raw if args.verbose else summarize_network(net_raw)
    print("\n[network_params]")
    print(json.dumps(enrich(net_out), indent=2, ensure_ascii=False))

    # USDT balance
    bal_raw = tools.get_usdt_balance(args.address)
    bal_out = bal_raw if args.verbose else summarize_usdt(bal_raw)
    print("\n[get_usdt_balance]")
    print(json.dumps(enrich(bal_out), indent=2, ensure_ascii=False))

    # Tx status (optional)
    if args.txid:
        tx_raw = tools.get_tx_status(args.txid)
        tx_out = tx_raw if args.verbose else summarize_tx(tx_raw)
        print("\n[get_tx_status]")
        print(json.dumps(enrich(tx_out), indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())

# python3 tool_smoke.py --address TPwjKc2nfSb6Zxk4sZDSZu6f9QaK3xktAP --verbose
# python3 tool_smoke.py --address TPwjKc2nfSb6Zxk4sZDSZu6f9QaK3xktAP
# python3 tool_smoke.py --address TPwjKc2nfSb6Zxk4sZDSZu6f9QaK3xktAP --txid 17c46bf2625aaf21b28a0c54783715d63380ccdb3d1134c8365e2628a5e2f6c4

