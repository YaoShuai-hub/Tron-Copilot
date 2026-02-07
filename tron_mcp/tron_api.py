"""Low-level HTTP helpers for TRONSCAN/TRONGRID."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import settings
from .utils.errors import UpstreamError

log = logging.getLogger(__name__)


def _build_request(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    data: Optional[bytes] = None,
) -> Request:
    """Construct a urllib Request with merged headers."""
    hdrs = {"Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    return Request(url=url, data=data, headers=hdrs, method=method)


def _inject_trongrid_key(url: str, headers: Dict[str, str]) -> None:
    """Attach TRON-PRO-API-KEY when hitting official Trongrid endpoints."""
    if settings.SETTINGS.trongrid_api_key and url.startswith(settings.SETTINGS.trongrid_base):
        headers.setdefault("TRON-PRO-API-KEY", settings.SETTINGS.trongrid_api_key)


def _inject_tronscan_key(url: str, headers: Dict[str, str]) -> None:
    """Attach TRON-PRO-API-KEY for TRONSCAN if provided."""
    if settings.SETTINGS.tronscan_api_key and url.startswith(settings.SETTINGS.tronscan_base):
        headers.setdefault("TRON-PRO-API-KEY", settings.SETTINGS.tronscan_api_key)


def fetch_json(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    body: Optional[Dict[str, Any]] = None,
) -> Any:
    hdrs = dict(headers or {})
    _inject_trongrid_key(url, hdrs)
    _inject_tronscan_key(url, hdrs)

    data_bytes = None
    if body is not None:
        data_bytes = json.dumps(body).encode("utf-8")
        hdrs["Content-Type"] = "application/json"

    req = _build_request(url, method=method, headers=hdrs, data=data_bytes)

    try:
        with urlopen(req, timeout=settings.SETTINGS.request_timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            text = resp.read().decode(charset, errors="replace")
            return json.loads(text)
    except HTTPError as err:
        detail = err.read().decode("utf-8", errors="replace") if err.fp else ""
        raise UpstreamError(
            f"HTTP {err.code} {err.reason}", status=err.code, body=detail
        ) from err
    except URLError as err:
        raise UpstreamError(f"Network error: {err.reason}") from err


# --- Specific API helpers ----------------------------------------------------

def fetch_account(address: str) -> Dict[str, Any]:
    """Fetch TRONSCAN account payload."""
    url = f"{settings.SETTINGS.tronscan_base}/account?address={address}"
    return fetch_json(url)


def fetch_account_trongrid(address: str) -> Dict[str, Any]:
    """Fetch account payload from TRONGRID (includes TRX balance)."""
    url = f"{settings.SETTINGS.trongrid_base}/wallet/getaccount"
    body = {"address": address, "visible": True}
    return fetch_json(url, method="POST", body=body)


def fetch_chain_parameters() -> Dict[str, Any]:
    """Fetch chain parameters (energy fee, bandwidth fee, etc.)."""
    url = f"{settings.SETTINGS.trongrid_base}/wallet/getchainparameters"
    return fetch_json(url, method="POST", body={})


def fetch_tx_meta(txid: str) -> Dict[str, Any]:
    """Get lightweight tx metadata (exists/pending)."""
    url = f"{settings.SETTINGS.trongrid_base}/wallet/gettransactionbyid"
    return fetch_json(url, method="POST", body={"value": txid})


def fetch_tx_info(txid: str) -> Dict[str, Any]:
    """Get confirmed tx receipt info (fee, block, status)."""
    url = f"{settings.SETTINGS.trongrid_base}/wallet/gettransactioninfobyid"
    return fetch_json(url, method="POST", body={"value": txid})


# --- Activity / listings ----------------------------------------------------

def fetch_transactions(address: str, limit: int = 20, start: int = 0) -> Dict[str, Any]:
    """Fetch recent transactions for an address (TRONGRID v1)."""
    fp = f"&fingerprint={start}" if start else ""
    url = (
        f"{settings.SETTINGS.trongrid_base}/v1/accounts/{address}/transactions"
        f"?limit={limit}{fp}"
    )
    return fetch_json(url)


def fetch_trc20_transfers(address: str, limit: int = 20, start: int = 0) -> Dict[str, Any]:
    """Fetch TRC20 transfers related to an address (TRONGRID v1)."""
    fp = f"&fingerprint={start}" if start else ""
    url = (
        f"{settings.SETTINGS.trongrid_base}/v1/accounts/{address}/transactions/trc20"
        f"?limit={limit}{fp}"
    )
    return fetch_json(url)


# --- Tronscan fallback ------------------------------------------------------

def fetch_transactions_tronscan(address: str, limit: int = 20, start: int = 0) -> Dict[str, Any]:
    """Fetch recent transactions for an address (TRONSCAN) as fallback."""
    url = (
        f"{settings.SETTINGS.tronscan_base}/transaction"
        f"?address={address}&limit={limit}&start={start}&sort=-timestamp"
    )
    return fetch_json(url)


def fetch_trc20_transfers_tronscan(address: str, limit: int = 20, start: int = 0) -> Dict[str, Any]:
    """Fetch TRC20 transfers related to an address (TRONSCAN) as fallback."""
    url = (
        f"{settings.SETTINGS.tronscan_base}/token_trc20/transfers"
        f"?relatedAddress={address}&limit={limit}&start={start}&sort=-timestamp"
    )
    return fetch_json(url)


# --- Transaction building ---------------------------------------------------

def create_trx_transfer(
    owner_address: str,
    to_address: str,
    amount_sun: int,
) -> Dict[str, Any]:
    """Create an unsigned TRX transfer transaction (TRONGRID).

    Note: uses visible=true to accept Base58 addresses.
    """
    url = f"{settings.SETTINGS.trongrid_base}/wallet/createtransaction"
    body = {
        "owner_address": owner_address,
        "to_address": to_address,
        "amount": int(amount_sun),
        "visible": True,
    }
    return fetch_json(url, method="POST", body=body)


def trigger_smart_contract(
    owner_address: str,
    contract_address: str,
    function_selector: str,
    parameter: str,
    fee_limit: int = 30_000_000,
    call_value: int = 0,
    visible: bool = True,
) -> Dict[str, Any]:
    """Create an unsigned smart contract invocation (TRONGRID)."""
    url = f"{settings.SETTINGS.trongrid_base}/wallet/triggersmartcontract"
    body = {
        "owner_address": owner_address,
        "contract_address": contract_address,
        "function_selector": function_selector,
        "parameter": parameter,
        "fee_limit": int(fee_limit),
        "call_value": int(call_value),
        "visible": bool(visible),
    }
    return fetch_json(url, method="POST", body=body)


def broadcast_transaction(signed_tx: Dict[str, Any]) -> Dict[str, Any]:
    """Broadcast a signed transaction to the network (TRONGRID)."""
    url = f"{settings.SETTINGS.trongrid_base}/wallet/broadcasttransaction"
    return fetch_json(url, method="POST", body=signed_tx)
