import httpx
from src.config import Config
from typing import Dict, Any, Optional

class TronClient:

    def __init__(self):
        self.node_url = Config.TRON_NODE_URL
        self.scan_url = Config.TRONSCAN_URL
        
        # Headers for TronGrid
        self.headers = {
            "TRON-PRO-API-KEY": Config.TRONGRID_API_KEY if Config.TRONGRID_API_KEY else "",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
        }
        self.client = httpx.AsyncClient(headers=self.headers, timeout=Config.TIMEOUT)

    async def get_test_data(self) -> Dict[str, Any]:
        """Test connection to TRON network."""
        try:
            response = await self.client.post(f"{self.node_url}/wallet/getnowblock")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    async def get_account_tokens(self, address: str) -> Dict[str, Any]:
        """Fetch all token balances (TRX, TRC10, TRC20) from TronScan."""
        try:
            # TronScan API is convenient for aggregated token data
            url = f"{self.scan_url}/account/tokens"
            params = {
                "address": address,
                "start": 0,
                "limit": 50,
                "hidden": 0,
                "show": 0,
                "sortType": 0
            }
            # Note: TronScan API uses its own rate limits, usually generous for public use
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    async def get_token_price(self, symbol: str) -> float:
        """Get token price in USD. Uses CoinGecko or TronScan."""
        try:
            # Simple fallback to CoinGecko for major tokens
            # For TRON specific tokens, we might need SunSwap API or DexScreener
            
            # Map symbol to CoinGecko ID
            symbol_map = {
                "TRX": "tron",
                "USDT": "tether",
                "USDD": "usdd",
                "BTT": "bittorrent"
            }
            
            # Fallback to Binance for major tokens (More reliable without key)
            if symbol.upper() in ["TRX", "USDT", "BTC", "ETH"]:
                binance_symbol = f"{symbol.upper()}USDT"
                if symbol.upper() == "USDT":
                    return 1.0
                try:
                    b_url = "https://api.binance.com/api/v3/ticker/price"
                    resp = await self.client.get(b_url, params={"symbol": binance_symbol})
                    if resp.status_code == 200:
                        return float(resp.json()["price"])
                except:
                    pass

            if symbol.upper() in symbol_map:
                cg_id = symbol_map[symbol.upper()]
                url = "https://api.coingecko.com/api/v3/simple/price"
                params = {"ids": cg_id, "vs_currencies": "usd"}
                # Create a new client without TronGrid headers for CoinGecko to avoid confusion? 
                # Actually headers are fine, usually ignored.
                response = await self.client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    return data.get(cg_id, {}).get("usd", 0.0)
            
            # Fallback or specific implementation for other tokens can go here
            return 0.0
        except Exception as e:
            print(f"Error fetching price: {e}")
            return 0.0


    async def trigger_constant_contract(
        self, 
        owner_address: str, 
        contract_address: str, 
        function_selector: str, 
        parameter: str,
        visible: bool = True
    ) -> Dict[str, Any]:
        """
        Trigger a constant contract (view function or dry run).
        """
        try:
            url = f"{self.node_url}/wallet/triggerconstantcontract"
            payload = {
                "owner_address": owner_address,
                "contract_address": contract_address,
                "function_selector": function_selector,
                "parameter": parameter,
                "visible": visible
            }
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    async def close(self):
        await self.client.aclose()
