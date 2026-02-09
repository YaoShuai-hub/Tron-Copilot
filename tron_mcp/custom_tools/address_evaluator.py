"""
地址评价工具 - 查询地址交易记录并进行智能锐评
"""

import json
from datetime import datetime
from typing import Dict, List, Any

# 导入主服务模块的工具函数
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

TOOL_DEFINITIONS = [
    {
        "name": "evaluate_address",
        "description": "深度分析地址交易行为并给出锐评",
        "parameters": {
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "TRON地址 (Base58格式，以T开头)"
                },
                "limit": {
                    "type": "integer",
                    "description": "查询交易数量，默认20",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 50
                }
            },
            "required": ["address"]
        }
    }
]

def call_tool(tool_name: str, params: Dict[str, Any]) -> str:
    """工具调用入口"""
    if tool_name == "evaluate_address":
        return evaluate_address(params.get("address"), params.get("limit", 20))
    else:
        return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)

def evaluate_address(address: str, limit: int = 20) -> str:
    """
    评价地址的交易行为
    
    Args:
        address: TRON地址
        limit: 查询交易数量
    
    Returns:
        JSON格式的评价结果
    """
    try:
        # 导入工具函数
        from main import get_recent_transactions, get_address_labels, get_wallet_balance
        
        # 获取最近交易记录
        transactions_result = get_recent_transactions({"address": address, "limit": limit})
        
        if isinstance(transactions_result, str):
            transactions_data = json.loads(transactions_result)
        else:
            transactions_data = transactions_result
            
        # 获取地址标签信息
        labels_result = get_address_labels({"address": address})
        if isinstance(labels_result, str):
            labels_data = json.loads(labels_result)
        else:
            labels_data = labels_result
        
        # 获取余额信息
        try:
            balance_result = get_wallet_balance({"address": address})
            if isinstance(balance_result, str):
                balance_data = json.loads(balance_result)
            else:
                balance_data = balance_result
        except:
            balance_data = {"trx_balance": "未知", "total_value_usd": "未知"}
        
        # 分析交易数据
        analysis = analyze_transactions(transactions_data, address)
        
        # 生成锐评
        roasting = generate_roasting(analysis, labels_data, balance_data)
        
        result = {
            "address": address,
            "evaluation_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "address_info": {
                "labels": labels_data.get("labels", []),
                "is_contract": labels_data.get("is_contract", False),
                "name": labels_data.get("name", "未知")
            },
            "balance_info": {
                " "trx_balance": balance_data.get("trx_balance", "未知"),
                "total_value_usd": balance_data.get("total_value_usd", "未知")
            },
            "transaction_analysis": analysis,
            "roasting": roasting
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"评价失败: {str(e)}",
            "address": address
        }, ensure_ascii=False)

def analyze_transactions(transactions_data: Dict, address: str) -> Dict:
    """分析交易数据"""
    items = transactions_data.get("items", [])
    
    if not items:
        return {
            "total_transactions": 0,
            "message": "该地址暂无交易记录"
        }
    
    # 统计指标
    total_tx = len(items)
    sent_count = 0
    received_count = 0
    self_count = 0
    total_sent_amount = 0
    total_received_amount = 0
    unique_addresses = set()
    timestamps = []
    
    for tx in items:
        from_addr = tx.get("from", "")
        to_addr = tx.get("to", "")
        amount = tx.get("amount", 0)
        timestamp = tx.get("timestamp", 0)
        
        timestamps.append(timestamp)
        unique_addresses.add(from_addr)
        unique_addresses.add(to_addr)
        
        if from_addr == address and to_addr == address:
            self_count += 1
        elif from_addr == address:
            sent_count += 1
            total_sent_amount += amount
        elif to_addr == address:
            received_count += 1
            total_received_amount += amount
    
    # 计算时间分布
    if timestamps:
        timestamps.sort()
        time_span = (timestamps[-1] - timestamps[0]) / 1000  # 转换为秒
        time_span_hours = time_span / 3600
        time_span_days = time_span / 86400
    else:
        time_span_hours = 0
        time_span_days = 0
    
    # 计算交易频率
    if time_span_hours > 0:
        tx_per_hour = total_tx / time_span_hours
        tx_per_per_day = total_tx / time_span_days if time_span_days > 0 else 0
    else:
        tx_per_hour = 0
        tx_per_day = 0
    
    return {
        "total_transactions": total_tx,
        "sent_transactions": sent_count,
        "received_transactions": received_count,
        "self_transactions": self_count,
        "total_sent": total_sent_amount,
        "total_received": total_received_amount,
        "unique_addresses": len(unique_addresses) - 1,  # 减去自己
        "time_span_hours": round(time_span_hours, 2),
        "time_span_days": round(time_span_days, 2),
        "transactions_per_hour": round(tx_per_hour, 2),
        "transactions_per_day": round(tx_per_day, 2),
        "net_flow": total_received_amount - total_sent_amount
    }

def generate_roasting(analysis: Dict, labels_data: Dict, balance_data: Dict) -> Dict:
    """生成锐评"""
    roasts = []
    tags = []
    score = 50  # 基础分
    
    total_tx = analysis.get("total_transactions", 0)
    
    if total_tx == 0:
        return {
            "overall_score": 30,
            "roast_comments": ["这个地址是个安静的美男子，一笔交易都没有，是在等待什么吗？"],
            "tags": ["沉睡账户", "零交易"],
            "activity_level": "沉睡"
        }
    
    # 活跃度分析
    tx_per_day = analysis.get("transactions_per_day", 0)
    if tx_per_day > 10:
        roasts.append("💀 交易频率爆表！这地址比我的心跳还快，绝对是交易机器或者重度用户！")
        tags.append("高频交易")
        score += 20
    elif tx_per_day > 1:
        roasts.append("📈 活跃度不错，每天都有交易记录，是个勤快的地址。")
        tags.append("活跃用户")
        score += 10
    elif tx_per_day > 0.1:
        roasts.append("😐 偶尔冒个泡，交易频率一般，可能是普通用户。")
        tags.append("普通用户")
    else:
        roasts.append("🐌 交易频率低得惊人，这地址是在冬眠吗？")
        tags.append("低频交易")
        score -= 10
    
    # 交易方向分析
    sent_count = analysis.get("sent_transactions", 0)
    received_count = analysis.get("received_transactions", 0)
    
    if sent_count > received_count * 3:
        roasts.append("🎁 散财童子！转出的交易远多于转入，是个慷慨的地址（或者被薅羊毛了）！")
        tags.append("转出为主")
        score += 5
    elif received_count > sent_count * 3:
        roasts.append("💰 聚宝盆！收到的交易远多于转出，是个受欢迎的地址（或者羊毛大户）！")
        tags.append("转入为主")
               score += 5
    elif sent_count == 0 and received_count > 0:
        roasts.append("🎯 纯接收地址，只进不出，是个守财奴！")
        tags.append("只进不出")
    elif received_count == 0 and sent_count > 0:
        roasts.append("🚀 纯发送地址，只出不进，是个散财童子！")
        tags.append("只出不进")
    
    # 金额分析
    net_flow = analysis.get("net_flow", 0)
    if net_flow > 1000000:  # 1 TRX以上
        roasts.append("📈 净流入地址，资金在积累，是个有财气的地址！")
        tags.append("净流入")
        score += 10
    elif net_flow < -1000000:
        roasts.append("📉 净流出地址，资金在减少，是个慷慨的地址（或者被洗劫了）！")
        tags.append("净流出")
        score -= 5
    
    # 交互对象分析
    unique_addresses = analysis.get("unique_addresses", 0)
    if unique_addresses > 20:
        roasts.append(f"🌐 社交达人！和{unique_addresses}个不同地址有过交互，人脉广阔！")
        tags.append("社交达人")
        score += 10
    elif unique_addresses > 5:
        roasts.append(f"👥 交互对象适中，和{unique_addresses}个地址有过往来。")
        tags.append("正常交互")
    elif unique_addresses <= 2:
        roasts.append("🔒 交互对象单一，可能是专用账户或者隐私保护意识强。")
        tags.append("交互单一")
    
    # 合约标签分析
    if labels_data.get("is_contract", False):
        roasts.append("🤖 这是一个合约地址，不是普通用户地址！")
        tags.append("智能合约")
        score += 15
    
    # 时间跨度分析
    time_span_days = analysis.get("time_span_days", 0)
    if time_span_days > 30:
        roasts.append(f"📅 老玩家！交易记录跨越{time_span_days:.1f}天，是个有历史的地址。")
        tags.append("老玩家")
        score += 5
    elif time_span_days < 1:
        roasts.append("🆕 新手！交易记录都在一天内，可能是刚创建的地址。")
        tags.append("新地址")
    
    # 余额分析
    try:
        balance = float(balance_data.get("trx_balance", 0))
        if balance > 1000:
            roasts.append("💎 富豪！余额超过1000 TRX，是个有钱的地址！")
            tags.append("富豪")
            score += 15
        elif balance > 100:
            roasts.append("💵 小康！余额还不错，是个有资产的地址。")
            tags.append("小康")
            score += 5
        elif balance < 1:
            roasts.append("💸 余额紧张，这个地址可能需要充值了。")
            tags.append("余额紧张")
            score -= 10
    except:
        pass
    
    # 综合评分调整
    score = max(0, min(100, score))
    
    # 活跃等级
    if score >= 80:
        activity_level = "大神级"
    elif score >= 60:
        activity_level = "活跃级"
    elif score >= 40:
        activity_level = "普通级"
    else:
        activity_level = "萌新级"
    
    return {
        "overall_score": score,
        "roast_comments": roasts,
        "tags": tags,
        "activity_level": activity_level
    }