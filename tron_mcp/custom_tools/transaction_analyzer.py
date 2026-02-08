"""
交易记录分析工具 - 查询100条交易记录并进行深度分析
"""
from typing import Dict, Any, List
from datetime import datetime
import json

TOOL_DEFINITIONS = [
    {
        "name": "analyze_transactions_100",
        "description": "查询并分析指定地址的100条交易记录，包括TRX和TRC20交易，提供详细的统计分析",
        "parameters": {
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "TRON地址 (Base58格式，以T开头)"
                },
                "include_trc20": {
                    "type": "boolean",
                    "description": "是否包含TRC20代币转账记录",
                    "default": True
                },
                "detailed_analysis": {
                    "type": "boolean",
                    "description": "是否进行详细分析（包括时间分布、金额分布等）",
                    "default": True
                }
            },
            "required": ["address"]
        }
    }
]

def call_tool(tool_name: str, params: Dict[str, Any]) -> Any:
    """调用外部工具的函数"""
    pass

def analyze_transactions_100(
    address: str, 
    include_trc20: bool = True,
    detailed_analysis: bool = True
) -> str:
    """
    查询并分析100条交易记录
    """
    analysis_result = {
        "address": address,
        "analysis_timestamp": datetime.now().isoformat(),
        "summary": {
            "total_transactions": 0,
            "trx_count": 0,
            "trc20_count": 0,
            "time_range": {"earliest": None, "latest": None}
        },
        "trx_data": [],
        "trc20_data": [],
        "analysis": {}
    }
    
    # 1. 获取TRX交易记录
    try:
        # 尝试获取更多交易记录
        all_trx = []
        
        # 第一次调用
        result1 = call_tool("get_recent_transactions", {"address": address, "limit": 50})
        if result1:
            if isinstance(result1, str):
                try:
                    result1 = json.loads(result1)
                except:
                    result1 = {"data": []}
            
            if isinstance(result1, dict) and "data" in result1:
                all_trx.extend(result1["data"])
            elif isinstance(result1, list):
                all_trx.extend(result1)
        
        # 第二次调用（获取更多）
        if len(all_trx) < 100:
            result2 = call_tool("get_recent_transactions", {"address": address, "limit": 50})
            if result2:
                if isinstance(result2, str):
                    try:
                        result2 = json.loads(result2)
                    except:
                        result2 = {"data": []}
                
                if isinstance(result2, dict) and "data" in result2:
                    # 去重
                    existing_ids = {tx.get("txID", tx.get("hash", "")) for tx in all_trx}
                    for tx in result2["data"]:
                        tx_id = tx.get("txID", tx.get("hash", ""))
                        if tx_id and tx_id not in existing_ids:
                            all_trx.append(tx)
                elif isinstance(result2, list):
                    existing_ids = {tx.get("txID", tx.get("hash", "")) for tx in all_trx}
                    for tx in result2:
                        tx_id = tx.get("txID", tx.get("hash", ""))
                        if tx_id and tx_id not in existing_ids:
                            all_trx.append(tx)
        
        analysis_result["trx_data"] = all_trx[:100]
        analysis_result["summary"]["trx_count"] = len(analysis_result["trx_data"])
        
    except Exception as e:
        analysis_result["trx_error"] = str(e)
    
    # 2. 获取TRC20交易记录
    if include_trc20:
        try:
            all_trc20 = []
            
            # 第一次调用
            result1 = call_tool("get_trc20_transfers", {"address": address, "limit": 50})
            if result1:
                if isinstance(result1, str):
                    try:
                        result1 = json.loads(result1)
                    except:
                        result1 = {"data": []}
                
                if isinstance(result1, dict) and "data" in result1:
                    all_trc20.extend(result1["data"])
                elif isinstance(result1, list):
                    all_trc20.extend(result1)
            
            # 第二次调用
            if len(all_trc20) < 100:
                result2 = call_tool("get_trc20_transfers", {"address": address, "limit": 50})
                if result2:
                    if isinstance(result2, str):
                        try:
                            result2 = json.loads(result2)
                        except:
                            result2 = {"data": []}
                    
                    if isinstance(result2, dict) and "data" in result2:
                        existing_ids = {tx.get("transaction_id", tx.get("txID", "")) for tx in all_trc20}
                        for tx in result2["data"]:
                            tx_id = tx.get("transaction_id", tx.get("txID", ""))
                            if tx_id and tx_id not in existing_ids:
                                all_trc20.append(tx)
                    elif isinstance(result2, list):
                        existing_ids = {tx.get("transaction_id", tx.get("txID", "")) for tx in all_trc20}
                        for tx in result2:
                            tx_id = tx.get("transaction_id", tx.get("txID", ""))
                            if tx_id and tx_id not in existing_ids:
                                all_trc20.append(tx)
            
            analysis_result["trc20_data"] = all_trc20[:100]
            analysis_result["summary"]["trc20_count"] = len(analysis_result["trc20_data"])
            
        except Exception as e:
            analysis_result["trc20_error"] = str(e)
    
    # 3. 更新总交易数
    analysis_result["summary"]["total_transactions"] = (
        analysis_result["summary"]["trx_count"] + 
        analysis_result["summary"]["trc20_count"]
    )
    
    # 4. 进行详细分析
    if detailed_analysis:
        analysis_result["analysis"] = perform_detailed_analysis(
            analysis_result["trx_data"],
            analysis_result["trc20_data"],
            address
        )
    
    return json.dumps(analysis_result, ensure_ascii=False, indent=2)

def perform_detailed_analysis(trx_transactions: List, trc20_transactions: List, address: str) -> Dict:
    """
    执行详细的交易分析
    """
    analysis = {
        "trx_analysis": {},
        "trc20_analysis": {},
        "overall_insights": []
    }
    
    # TRX交易分析
    if trx_transactions:
        trx_stats = {
            "total_transactions": len(trx_transactions),
            "incoming": {"count": 0, "total_amount": 0, "transactions": []},
            "outgoing": {"count": 0, "total_amount": 0, "transactions": []},
            "counterparties": set(),
            "amount_distribution": {"min": float('inf'), "max": 0, "avg": 0, "total": 0},
            "time_distribution": {}
        }
        
        for tx in trx_transactions:
            if not isinstance(tx, dict):
                continue
                
            try:
                # 获取交易信息
                to_addr = tx.get("to", "")
                from_addr = tx.get("from", "")
                amount_str = tx.get("value", "") or tx.get("amount", "") or "0"
                timestamp = tx.get("timestamp", 0)
                
                # 解析金额 (TRX, 1 TRX = 1,000,000 sun)
                try:
                    amount = float(amount_str) / 1_000_000 if amount_str else 0
                except:
                    amount = 0
                
                # 判断交易方向
                is_incoming = False
                if to_addr and to_addr.lower() == address.lower():
                    is_incoming = True
                    trx_stats["incoming"]["count"] += 1
                    trx_stats["incoming"]["total_amount"] += amount
                    if len(trx_stats["incoming"]["transactions"]) < 10:  # 只保留前10个示例
                        trx_stats["incoming"]["transactions"].append({
                            "amount": amount,
                            "from": from_addr,
                            "timestamp": timestamp
                        })
                elif from_addr and from_addr.lower() == address.lower():
                    trx_stats["outgoing"]["count"] += 1
                    trx_stats["outgoing"]["total_amount"] += amount
                    if len(trx_stats["outgoing"]["transactions"]) < 10:
                        trx_stats["outgoing"]["transactions"].append({
                            "amount": amount,
                            "to": to_addr,
                            "timestamp": timestamp
                        })
                
                # 收集交易对手方
                if to_addr and to_addr.lower() != address.lower():
                    trx_stats["counterparties"].add(to_addr)
                if from_addr and from_addr.lower() != address.lower():
                    trx_stats["counterparties"].add(from_addr)
                
                # 金额分布统计
                if amount > 0:
                    trx_stats["amount_distribution"]["total"] += amount
                    trx_stats["amount_distribution"]["min"] = min(trx_stats["amount_distribution"]["min"], amount)
                    trx_stats["amount_distribution"]["max"] = max(trx_stats["amount_distribution"]["max"], amount)
                
            except Exception as e:
                continue
        
        # 计算平均金额
        if trx_stats["amount_distribution"]["total"] > 0:
            valid_count = sum(1 for tx in trx_transactions if isinstance(tx, dict))
            trx_stats["amount_distribution"]["avg"] = (
                trx_stats["amount_distribution"]["total"] / valid_count
                if valid_count > 0 else 0
            )
        
        # 重置min为0如果没有交易
        if trx_stats["amount_distribution"]["min"] == float('inf'):
            trx_stats["amount_distribution"]["min"] = 0
        
        # 转换set为list
        trx_stats["counterparties"] = list(trx_stats["counterparties"])
        trx_stats["unique_counterparty_count"] = len(trx_stats["counterparties"])
        
        # 计算净流量
        trx_stats["net_flow"] = trx_stats["incoming"]["total_amount"] - trx_stats["outgoing"]["total_amount"]
        
        analysis["trx_analysis"] = trx_stats
    
    # TRC20交易分析
    if trc20_transactions:
        trc20_stats = {
            "total_transactions": len(trc20_transactions),
            "incoming": {"count": 0, "by_token": {}},
            "outgoing": {"count": 0, "by_token": {}},
            "tokens": {},
            "counterparties": set()
        }
        
        for tx in trc20_transactions:
            if not isinstance(tx, dict):
                continue
                
            try:
                to_addr = tx.get("to", "")
                from_addr = tx.get("from", "")
                amount_str = tx.get("value", "") or tx.get("amount", "") or "0"
                token_symbol = tx.get("token_symbol", "UNKNOWN")
                contract = tx.get("contract_address", "")
                
                # 解析金额
                try:
                    amount = float(amount_str)
                except:
                    amount = 0
                
                # 判断交易方向
                if to_addr and to_addr.lower() == address.lower():
                    trc20_stats["incoming"]["count"] += 1
                    if token_symbol not in trc20_stats["incoming"]["by_token"]:
                        trc20_stats["incoming"]["by_token"][token_symbol] = 0
                    trc20_stats["incoming"]["by_token"][token_symbol] += amount
                elif from_addr and from_addr.lower() == address.lower() and amount > 0:
                    trc20_stats["outgoing"]["count"] += 1
                    if token_symbol not in trc20_stats["outgoing"]["by_token"]:
                        trc20_stats["outgoing"]["by_token"][token_symbol] = 0
                    trc20_stats["outgoing"]["by_token"][token_symbol] += amount
                
                # 代币统计
                if token_symbol not in trc20_stats["tokens"]:
                    trc20_stats["tokens"][token_symbol] = {
                        "contract": contract,
                        "transaction_count": 0,
                        "total_volume": 0
                    }
                trc20_stats["tokens"][token_symbol]["transaction_count"] += 1
                trc20_stats["tokens"][token_symbol]["total_volume"] += amount
                
                # 收集交易对手方
                if to_addr and to_addr.lower() != address.lower():
                    trc20_stats["counterparties"].add(to_addr)
                if from_addr and from_addr.lower() != address.lower():
                    trc20_stats["counterparties"].add(from_addr)
                    
            except Exception as e:
                continue
        
        trc20_stats["counterparties"] = list(trc20_stats["counterparties"])
        trc20_stats["unique_counterparty_count"] = len(trc20_stats["counterparties"])
        trc20_stats["unique_token_count"] = len(trc20_stats["tokens"])
        
        analysis["trc20_analysis"] = trc20_stats
    
    # 生成整体洞察
    insights = []
    
    if analysis.get("trx_analysis"):
        trx = analysis["trx_analysis"]
        if trx["net_flow"] > 0:
            insights.append(f"TRX净流入: {trx['net_flow']:.2f} TRX")
        elif trx["net_flow"] < 0:
            insights.append(f"TRX净流出: {abs(trx['net_flow']):.2f} TRX")
        
        if trx["unique_counterparty_count"] > 0:
            insights.append(f"与{trx['unique_counterparty_count']}个不同地址进行过TRX交易")
    
    if analysis.get("trc20_analysis"):
        trc20 = analysis["trc20_analysis"]
        if trc20["unique_token_count"] > 0:
            tokens = list(trc20["tokens"].keys())
            insights.append(f"涉及{trc20['unique_token_count']}种代币: {', '.join(tokens[:5])}")
        
        if trc20["unique_counterparty_count"] > 0:
            insights.append(f"与{trc20['unique_counterparty_count']}个不同地址进行过代币交易")
    
    total_tx = len(trx_transactions) + len(trc20_transactions)
    if total_tx > 0:
        insights.append(f"分析完成，共处理{total_tx}条交易记录")
    
    analysis["overall_insights"] = insights
    
    return analysis