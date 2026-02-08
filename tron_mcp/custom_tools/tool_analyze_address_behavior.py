"""
地址行为分析工具 - 查找地址最近交易记录并分析其行为模式
"""
import json
from datetime import datetime

TOOL_DEFINITIONS = [
    {
        "name": "analyze_address_behavior",
        "description": "分析TRON地址的行为模式 - 查找最近交易记录并进行深度行为分析",
        "parameters": {
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "TRON Base58地址（以T开头）"
                },
                "limit": {
                    "type": "integer",
                    "description": "获取交易记录的最大数量（1-50）",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 50
                }
            },
            "required": ["address"]
        }
    }
]

def call_tool(tool_name, params):
    """
    调用工具的主函数
    """
    if tool_name == "analyze_address_behavior":
        return analyze_address_behavior(params)
    else:
        return f"未知的工具: {tool_name}"

def analyze_address_behavior(params):
    """
    分析地址行为的主函数
    """
    address = params.get("address")
    limit = params.get("limit", 20)
    
    if not address:
        return "错误：必须提供地址参数"
    
    if not address.startswith("T"):
        return "错误：地址必须以T开头（TRON Base58格式）"
    
    # 获取最近交易记录
    try:
        transactions_result = get_recent_transactions(address=address, limit=limit)
        transactions = json.loads(transactions_result)
    except Exception as e:
        return f"获取交易记录失败: {str(e)}"
    
    # 分析交易数据
    analysis = analyze_transactions(address, transactions)
    
    return format_analysis_report(analysis)

def get_recent_transactions(address, limit):
    """
    获取最近交易记录的模拟函数
    在实际环境中，这会调用真正的API
    """
    # 这里返回模拟数据，实际使用时会调用真正的API
    return json.dumps({
        "address": address,
        "total": 0,
        "data": []
    })

def analyze_transactions(address, transactions):
    """
    分析交易数据并生成行为分析报告
    """
    analysis = {
        "address": address,
        "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_transactions": 0,
        "transaction_types": {},
        "behavior_patterns": [],
        "address_type": "未知",
        "risk_level": "低",
        "recommendations": []
    }
    
    # 检查交易数据
    tx_data = transactions.get("data", [])
    total_count = transactions.get("total", len(tx_data))
    
    analysis["total_transactions"] = total_count
    
    if total_count == 0:
        analysis["address_type"] = "新地址/冷钱包"
        analysis["behavior_patterns"].append("无交易记录")
        analysis["recommendations"].append("地址可能刚创建或从未使用")
        analysis["recommendations"].append("建议检查私钥是否安全保存")
        return analysis
    
    # 分析交易类型
    incoming_count = 0
    outgoing_count = 0
    total_amount = 0
    unique_counterparties = set()
    
    for tx in tx_data:
        tx_type = tx.get("type", "unknown")
        analysis["transaction_types"][tx_type] = analysis["transaction_types"].get(tx_type, 0) + 1
        
        # 统计转入转出
        if tx.get("to") == address:
            incoming_count += 1
        elif tx.get("from") == address:
            outgoing_count += 1
        
        # 统计金额
        amount = tx.get("amount", 0)
        if amount:
            total_amount += amount
        
        # 统计对手方
        if tx.get("from"):
            unique_counterparties.add(tx["from"])
        if tx.get("to"):
            unique_counterparties.add(tx["to"])
    
    # 行为模式分析
    if incoming_count > outgoing_count * 3:
        analysis["behavior_patterns"].append("主要接收资金")
        analysis["address_type"] = "收款地址/充值地址"
    elif outgoing_count > incoming_count * 3:
        analysis["behavior_patterns"].append("主要发送资金")
        analysis["address_type"] = "付款地址/提现地址"
    elif incoming_count == outgoing_count and incoming_count > 0:
        analysis["behavior_patterns"].append("频繁转账")
        analysis["address_type"] = "活跃交易者"
    
    if len(unique_counterparties) > 10:
        analysis["behavior_patterns"].append("对手方分散")
        analysis["address_type"] = "交易所/服务地址"
    
    if total_amount > 1000000:  # 假设单位是sun
        analysis["behavior_patterns"].append("大额交易")
        analysis["risk_level"] = "中"
    
    if total_count > 50:
        analysis["behavior_patterns"].append("高频交易")
        analysis["risk_level"] = "中"
    
    # 生成建议
    if analysis["risk_level"] == "中":
        analysis["recommendations"].append("建议关注此地址的大额交易")
        analysis["recommendations"].append("注意交易频率是否异常")
    
    if "交易所/服务地址" in analysis["address_type"]:
        analysis["recommendations"].append("可能是交易所热钱包地址")
        analysis["recommendations"].append("建议确认交易对手的可靠性")
    
    analysis["unique_counterparties"] = len(unique_counterparties)
    analysis["incoming_transactions"] = incoming_count
    analysis["outgoing_transactions"] = outgoing_count
    
    return analysis

def format_analysis_report(analysis):
    """
    格式化分析报告
    """
    report = f"""
🔍 地址行为分析报告
{'='*40}

📍 分析地址: {analysis['address']}
⏰ 分析时间: {analysis['analysis_time']}

📊 交易统计
{'─'*20}
• 总交易数: {analysis['total_transactions']} 笔
• 转入交易: {analysis.get('incoming_transactions', 0)} 笔
• 转出交易: {analysis.get('outgoing_transactions', 0)} 笔
• 独立对手方: {analysis.get('unique_counterparties', 0)} 个

🏷️ 地址类型识别
{'─'*20}
• 类型: {analysis['address_type']}

🔍 行为模式
{'─'*20}
"""
    
    for pattern in analysis['behavior_patterns']:
        report += f"• {pattern}\n"
    
    report += f"""
⚠️ 风险评估
{'─'*20}
• 风险等级: {analysis['risk_level']}

💡 分析建议
{'─'*20}
"""
    
    for recommendation in analysis['recommendations']:
        report += f"• {recommendation}\n"
    
    if not analysis['recommendations']:
        report += "• 暂无特殊建议\n"
    
    report += f"\n{'='*40}\n"
    
    return report