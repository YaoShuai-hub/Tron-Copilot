"""
地址交易讽刺分析工具
查询地址历史交易并进行锐评分析
"""

import json
from datetime import datetime

TOOL_DEFINITIONS = [
    {
        "name": "roast_address_transactions",
        "description": "查询地址历史交易并进行讽刺性锐评分析（需要先调用get_recent_transactions获取数据）",
        "parameters": {
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "TRON Base58 地址"
                },
                "limit": {
                    "type": "integer",
                    "description": "查询交易数量限制，默认50",
                    "default": 50
                },
                "transaction_data": {
                    "type": "object",
                    "description": "可选：直接传入get_recent_transactions的返回数据进行锐评"
                }
            },
            "required": ["address"]
        }
    }
]

def call_tool(tool_name, args):
    """工具调用入口"""
    if tool_name == "roast_address_transactions":
        address = args.get("address")
        limit = args.get("limit", 50)
        tx_data = args.get("transaction_data")
        
        if tx_data:
            # 如果提供了交易数据，直接进行锐评
            return generate_roast(tx_data)
        else:
            # 返回需要获取交易数据的指令
            return {
                "action": "get_recent_transactions",
                "address": address,
                "limit": limit,
                "next_action": "roast_address_transactions"
            }
    else:
        return {"error": f"未知工具: {tool_name}"}

def generate_roast(analysis):
    """生成讽刺性评论"""
    tx_count = analysis.get("count", 0)
    items = analysis.get("items", [])
    address = analysis.get("address", "未知地址")
    
    if tx_count == 0:
        return {
            "address": address,
            "tx_count": 0,
            "roasts": [
                "🦭 这个地址比我的社交圈还干净，一笔交易都没有。",
                "💡 建议：检查一下地址是否正确，或者这个地址是不是刚出生。"
            ],
            "summary": f"地址 {address} 暂无交易记录"
        }
    
    # 分析交易模式
    in_txs = [tx for tx in items if tx.get("direction") == "IN"]
    out_txs = [tx for tx in items if tx.get("direction") == "OUT"]
    
    # 提取交互地址
    counterparties = set()
    for tx in items:
        if tx.get("direction") == "OUT":
            counterparties.add(tx.get("to", ""))
        else:
            counterparties.add(tx.get("from", ""))
    
    # 移除自己
    counterparties.discard(address)
    
    # 分析手续费模式
    fees = []
    for tx in items:
        if tx.get("ret") and len(tx.get("ret", [])) > 0:
            fee = tx.get("ret", [{}])[0].get("fee", 0)
            fees.append(fee)
    
    unique_fees = set(fees)
    avg_fee = sum(fees) / len(fees) if fees else 0
    
    # 时间分析
    timestamps = [tx.get("timestamp", 0) for tx in items if tx.get("timestamp")]
    if timestamps:
        time_span = max(timestamps) - min(timestamps)
        time_span_hours = time_span / (1000 * 3600)
        time_span_days = time_span_hours / 24
    else:
        time_span_hours = 0
        time_span_days = 0
    
    # 生成锐评
    roasts = []
    
    # 交易数量锐评
    if tx_count > 100:
        roasts.append(f"📊 **交易狂魔**: {tx_count}笔交易！这是把区块链当ATM机了吗？")
    elif tx_count > 50:
        roasts.append(f"📊 **活跃用户**: {tx_count}笔交易，看起来挺忙的，不知道在忙些什么...")
    elif tx_count > 20:
        roasts.append(f"📊 **中等活跃**: {tx_count}笔交易，不温不火，就像个打工人。")
    else:
        roasts.append(f"📊 **低调玩家**: {tx_count}笔交易，深藏不露。")
    
    # 出入账比例锐评
    if len(in_txs) == 0:
        roasts.append("💸 **只出不进**: 纯粹的散财童子！这种地址要么是土豪，要么是...咳咳。")
    elif len(out_txs) == 0:
        roasts.append("🎁 **只进不出**: 典型的貔貅属性，只吃不拉。")
    elif len(in_txs) > len(out_txs) * 2:
        ratio = len(in_txs) // max(len(out_txs), 1)
        roasts.append(f"📈 **净流入大户**: 收入是支出的{ratio}倍，这是在搞资金池吗？")
    elif len(out_txs) > len(in_txs) * 2:
        ratio = len(out_txs) // max(len(in_txs), 1)
        roasts.append(f"📉 **净流出大户**: 支出是收入的{ratio}倍，散财童子实锤了。")
    
    # 交互地址数量锐评
    if len(counterparties) <= 3:
        roasts.append(f"🎯 **固定圈子**: 只跟{len(counterparties)}个地址玩，这是在搞三人转还是资金循环？")
    elif len(counterparties) > 20:
        roasts.append(f"🌐 **社交达人**: 跟{len(counterparties)}个地址有交互，这是要竞选区块链村长吗？")
    else:
        roasts.append(f"🤝 **正常社交**: 与{len(counterparties)}个地址有过交互，中规中矩。")
    
    # 手续费锐评
    if len(unique_fees) == 1 and list(unique_fees)[0] == 268000:
        roasts.append("💰 **精准手续费**: 每笔都是0.268 TRX，这是什么玄学数字？强迫症实锤。")
    elif len(unique_fees) > 10:
        roasts.append("🎰 **手续费玩家**: 手续费变化多端，这是在玩手续费俄罗斯轮盘赌吗？")
    elif 0 in unique_fees and len(unique_fees) > 1:
        roasts.append("🆓 **零手续费爱好者**: 有些交易0手续费，这是在薅羊毛吗？")
    
    # 时间跨度锐评
    if time_span_hours < 1 and tx_count > 10:
        roasts.append("⚡ **瞬间爆发**: 短时间内疯狂交易，手指是不是得了帕金森？")
    elif time_span_days > 30:
        roasts.append("🐢 **长期玩家**: 交易跨度超过一个月，老韭菜了。")
    elif time_span_hours > 0 and time_span_hours < 24:
        roasts.append(f"🕐 **一日游**: 所有交易在{time_span_hours:.1f}小时内完成，这是在赶什么？")
    
    # 综合评价
    if len(counterparties) <= 3 and len(in_txs) > 0 and len(out_txs) > 0 and time_span_hours < 24:
        roasts.append("🚨 **可疑模式**: 固定圈子+高频出入账+短时间密集操作，这特征...建议远离。")
    
    # 检查是否有特定的可疑模式
    if len(counterparties) == 3 and len(in_txs) > 5 and len(out_txs) > 5:
        roasts.append("🔄 **资金循环**: 三方互转模式，资金就像在三个房间来回踢的皮球。")
    
    # 计算总手续费
    total_fee_trx = sum(fees) / 1_000_000  # 转换为TRX
    if total_fee_trx > 10:
        roasts.append(f"💸 **手续费大户**: 总共花费了{total_fee_trx:.2f} TRX手续费，真有钱！")
    
    return {
        "address": address,
        "tx_count": tx_count,
        "unique_counterparties": len(counterparties),
        "in_count": len(in_txs),
        "out_count": len(out_txs),
        "total_fee_trx": total_fee_trx,
        "time_span_hours": time_span_hours,
        "roasts": roasts,
        "summary": f"地址 {address} 共有 {tx_count} 笔交易，与 {len(counterparties)} 个不同地址交互，总手续费 {total_fee_trx:.4f} TRX。"
    }