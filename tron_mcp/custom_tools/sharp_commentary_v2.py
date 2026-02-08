"""
地址交易锐评工具 V2
自动分析TRON地址的交易行为并给出犀利点评
"""

import json
from datetime import datetime
from typing import Dict, List, Any

# 工具定义
TOOL_DEFINITIONS = [
    {
        "name": "sharp_commentary_v2",
        "description": "对TRON地址的交易行为进行犀利锐评分析，包括交易模式、频率、对手方分析等",
        "parameters": {
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "TRON地址（Base58格式，以T开头）"
                }
            },
            "required": ["address"]
        }
    }
]

def call_tool(tool_name: str, **kwargs):
    """
    调用其他工具的辅助函数
    """
    import sys
    import os
    
    # 添加项目根目录到路径
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    try:
        from tron_mcp.server import get_tool_function
        tool_func = get_tool_function(tool_name)
        if tool_func:
            return tool_func(**kwargs)
    except Exception as e:
        print(f"Error calling tool {tool_name}: {e}")
        return None
    
    return None

def sharp_commentary_v2(address: str) -> str:
    """
    对地址进行锐评分析的主函数
    """
    # 验证地址格式
    if not address or not address.startswith('T'):
        return "❌ 地址格式错误！请提供有效的TRON地址（以T开头）"
    
    # 收集数据
    try:
        # 获取TRX交易
        trx_result = call_tool("get_recent_transactions", address=address, limit=50)
        if not trx_result:
            trx_result = {"count": 0, "items": []}
        
        # 获取TRC20交易
        trc20_result = call_tool("get_trc20_transfers", address=address, limit=50)
        if not trc20_result:
            trc20_result = {"count": 0, "items": []}
        
        # 获取余额
        balance_result = call_tool("get_trx_balance", address=address)
        if not balance_result:
            balance_result = {"balance": {"human": "0"}}
        
        # 获取地址标签
        labels_result = call_tool("get_address_labels", address=address)
        if not labels_result:
            labels_result = {}
        
    except Exception as e:
        return f"❌ 数据获取失败：{str(e)}"
    
    # 分析数据
    analysis = analyze_transactions(
        trx_result.get("items", []),
        trc20_result.get("items", []),
        balance_result.get("balance", {}).get("human", "0"),
        labels_result
    )
    
    # 生成锐评
    commentary = generate_sharp_commentary(analysis, address)
    
    return commentary

def analyze_transactions(trx_transactions: List[Dict], trc20_transactions: List[Dict], 
                        balance: str, labels: Dict) -> Dict:
    """
    分析交易数据，提取关键指标
    """
    # 基础统计
    trx_count = len(trx_transactions)
    trc20_count = len(trc20_transactions)
    total_transactions = trx_count + trc20_count
    
    # 时间分析
    timestamps = []
    for tx in trx_transactions:
        if "timestamp" in tx:
            timestamps.append(tx["timestamp"])
    
    # 地址分析
    from_addresses = set()
    to_addresses = set()
    counterparties = set()
    
    for tx in trx_transactions:
        if "from" in tx:
            from_addresses.add(tx["from"])
        if "to" in tx:
            to_addresses.add(tx["to"])
        
        direction = tx.get("direction", "")
        if direction == "IN" and "from" in tx:
            counterparties.add(tx["from"])
        elif direction == "OUT" and "to" in tx:
            counterparties.add(tx["to"])
    
    # 移除自己
    self_address = ""
    if trx_transactions:
        self_address = trx_transactions[0].get("from", trx_transactions[0].get("to", ""))
    
    counterparties.discard(self_address)
    
    # 手续费分析
    total_fee = 0
    fee_transactions = 0
    for tx in trx_transactions:
        if "ret" in tx and len(tx["ret"]) > 0:
            fee = tx["ret"][0].get("fee", 0)
            total_fee += fee
            if fee > 0:
                fee_transactions += 1
    
    # 转账方向分析
    incoming = sum(1 for tx in trx_transactions if tx.get("direction") == "IN")
    outgoing = sum(1 for tx in trx_transactions if tx.get("direction") == "OUT")
    
    # 时间跨度
    time_span = 0
    if timestamps:
        time_span = (max(timestamps) - min(timestamps)) / 1000  # 转换为秒
    
    # 交易频率
    frequency = 0
    if time_span > 0:
        frequency = total_transactions / (time_span / 3600)  # 每小时交易数
    
    return {
        "trx_count": trx_count,
        "trc20_count": trc20_count,
        "total_transactions": total_transactions,
        "balance": balance,
        "counterparties": list(counterparties),
        "unique_counterparties": len(counterparties),
        "total_fee_sun": total_fee,
        "total_fee_trx": total_fee / 1_000_000,  # 转换为TRX
        "fee_transactions": fee_transactions,
        "incoming": incoming,
        "outgoing": outgoing,
        "time_span_hours": time_span / 3600 if time_span > 0 else 0,
        "frequency_per_hour": frequency,
        "labels": labels,
        "is_new_account": time_span < 86400 if time_span > 0 else False,  # 24小时内
        "is_high_frequency": frequency > 2,  # 每小时超过2笔
        "is_single_counterparty": len(counterparties) <= 1,
        "is_circular": len(counterparties) <= 3 and total_transactions > 10,  # 少量对手方但大量交易
        "trx_only": trc20_count == 0 and trx_count > 0,
        "no_transactions": total_transactions == 0
    }

def generate_sharp_commentary(analysis: Dict, address: str) -> str:
    """
    根据分析结果生成犀利锐评
    """
    if analysis["no_transactions"]:
        return f"""## 🎭 {address} 交易行为锐评报告

### 📊 基本信息
- **当前余额**: {analysis['balance']} TRX
- **交易总数**: 0笔
- **账户状态**: 🏝️ 无人问津的荒岛

### 🔥 讽刺锐评时间

**1. "佛系持币者"** 🧘
这个账户一笔交易都没有，就像一个买了房子却从来不装修的人。TRX躺在钱包里睡觉，连个翻身的机会都没有。

**2. "守财奴的典范"** 💰
在这个人人都想一夜暴富的时代，你却选择了"无为而治"。这种定力，连巴菲特都要给你点赞。

**3. "神秘的观察者"** 👁️
也许你是在等待什么？还是在观察什么？这种"潜伏"的行为，让人不禁怀疑你是不是在憋什么大招。

### 🎭 终极评价
**账户类型**: 典型的"潜水艇"账户
**危险等级**: ⭐ (安全到无聊)
**建议**: 要么动起来，就把TRX捐给有需要的人（比如我）😏

---
*（注：以上锐评纯属娱乐，如有雷同，纯属巧合）*
"""
    
    # 开始生成锐评
    commentary = f"""## 🎭 {address} 交易行为锐评报告

### 📊 基本信息
- **当前余额**: {analysis['balance']} TRX
- **TRX交易数**: {analysis['trx_count']}笔
- **TRC20交易数**: {analysis['trc20_count']}笔
- **交易总数**: {analysis['total_transactions']}笔
- **独立对手方**: {analysis['unique_counterparties']}个
- **总手续费**: {analysis['total_fee_trx']:.4f} TRX
- **入账次数**: {analysis['incoming']}笔
- **出账次数**: {analysis['outgoing']}笔
- **时间跨度**: {analysis['time_span_hours']:.2f}小时
- **交易频率**: {analysis['frequency_per_hour']:.2f}笔/小时

### 🔥 讽刺锐评时间

"""
    
    # 根据不同特征添加锐评
    comments = []
    
    # 高频交易
    if analysis["is_high_frequency"]:
        comments.append({
            "emoji": "🏃",
            "title": "「勤奋的搬砖工」",
            "content": f"这个账户在{analysis['time_span_hours']:.1f}小时内完成了{analysis['total_transactions']}笔交易，平均每小时{analysis['frequency_per_hour']:.1f}笔。这种「勤奋程度」，连华尔街的高频交易机器人都要自愧不如。可惜啊，搬的不是砖，是自己的手续费。"
        })
    
    # 单一对手方
    if analysis["is_single_counterparty"] and analysis["total_transactions"] > 5:
        comments.append({
            "emoji": "💑",
            "title": "「专一的恋人」",
            "content": f"整个交易历史就只有{analysis['unique_counterparties']}个固定对手方，这种「专一」让人感动。在这个花花世界里，你们俩的「真爱」简直是一股清流。不过话说回来，这么频繁的「私聊」，是不是在搞什么「内部消化」？"
        })
    
    # 循环交易
    if analysis["is_circular"]:
        comments.append({
            "emoji": "🎪",
            "title": "「三人行的寂寞」",
            "content": f"{analysis['unique_counterparties']}个地址来回转账，就像在玩什么神秘的多角恋游戏。钱从A转给你，你转给B，B又转回给你，循环往复，乐此不疲。这种封闭式的小圈子交易，怎么看都像是在搞什么「资金瑜伽」。"
        })
    
    # 只有TRX交易
    if analysis["trx_only"]:
        comments.append({
            "emoji": "💕",
            "title": "「TRX纯爱战士」",
            "content": f"{analysis['trx_count']}笔交易全是TRX，连个USDT的影子都没有。在这个USDT横行的年代，你居然对TRX如此专一？这种「纯粹」让人感动，也让人疑惑：是不是连个USDT合约都找不到？"
        })
    
    # 手续费大户
    if analysis["total_fee_trx"] > 10:
        comments.append({
            "emoji": "💸",
            "title": "「手续费贡献大户」",
            "content": f"{analysis['total_transactions']}笔交易光手续费就烧了{analysis['total_fee_trx']:.2f} TRX。按照这个速度，你这是在给孙宇晨打赏吗？这种「慷慨」程度，波场基金会应该给你发个「最佳贡献奖」。"
        })
    
    # 新账户
    if analysis["is_new_account"]:
        comments.append({
            "emoji": "👶",
            "title": "「急不可耐的新手」",
            "content": f"账户账户创建不到24小时就已经完成了{analysis['total_transactions']}笔交易。这种「急不可耐」的劲头，就像刚拿到驾照就上高速飙车的新手司机。年轻人，稳一点，路还长着呢。"
        })
    
    # 只有入账或只有出账
    if analysis["incoming"] > 0 and analysis["outgoing"] == 0:
        comments.append({
            "emoji": "🧺",
            "title": "「只进不出的貔貅」",
            "content": f"{analysis['incoming']}笔入账，0笔出账。这种「只进不出」的风格，活像个招财进宝的貔貅。不过小心点，太贪心容易消化不良哦。"
        })
    elif analysis["outgoing"] > 0 and analysis["incoming"] == 0:
        comments.append({
            "emoji": "🎁",
            "title": "「慷慨的散财童子」",
            "content": f"{analysis['outgoing']}笔出账，0笔入账。这种「只出不进」的豪爽，活像个散财童子。钱从哪里来不重要，重要的是送得开心，对吧？"
        })
    
    # 如果没有特殊特征，给个通用评价
    if not comments:
        comments.append({
            "emoji": "😐",
            "title": "「平平无奇的路人甲」",
            "content": f"这个账户的交易行为中规中矩，没什么特别的亮点。就像一杯白开水，解渴但无味。在这个充满戏剧性的区块链世界里，你选择做一个安静的旁观者，也是一种生活态度吧。"
        })
    
    # 添加评论到输出
    for i, comment in enumerate(comments, 1):
        commentary += f"**{i}. {comment['title']}** {comment['emoji']}\n"
        commentary += f"{comment['content']}\n\n"
    
    # 添加最终评价
    commentary += "### 🎭 终极评价\n"
    
    # 确定账户类型
    account_types = []
    if analysis["is_high_frequency"]:
        account_types.append("高频中转站")
    if analysis["is_circular"]:
        account_types.append("循环转账账户")
    if analysis["trx_only"]:
        account_types.append("TRX专用户")
    if analysis["is_new_account"]:
        account_types.append("急躁新账户")
    
    if not account_types:
        account_types.append("普通用户账户")
    
    # 确定危险等级
    danger_level = 1
    if analysis["is_high_frequency"]:
        danger_level += 1
    if analysis["is_circular"]:
        danger_level += 2
    if analysis["is_new_account"] and analysis["is_high_frequency"]:
        danger_level += 1
    
    danger_stars = "⭐" * min(danger_level, 5)
    danger_text = {
        1: "安全到无聊",
        2: "有点意思",
        3: "值得关注",
        4: "高度可疑",
        5: "五星好评，送给监管机构"
    }.get(min(danger_level, 5), "未知")
    
    commentary += f"**账户类型**: {', '.join(account_types)}\n"
    commentary += f"**危险等级**: {danger_stars} ({danger_text})\n"
    
    # 添加建议
    commentary += "**建议**: \n"
    suggestions = []
    if analysis["is_high_frequency"]:
        suggestions.append("这么高频的交易，小心把手续费烧穿了")
    if analysis["is_circular"]:
        suggestions.append("这种三人转游戏，小心被当成洗钱")
    if analysis["trx_only"]:
        suggestions.append("尝试接触一下USDT，外面的世界很精彩")
    if analysis["total_fee_trx"] > 10:
        suggestions.append("给波场贡献这么多手续费，孙宇晨应该给你发锦旗")
    
    if not suggestions:
        suggestions.append("继续保持，至少你看起来很正常")
    
    for i, suggestion in enumerate(suggestions, 1):
        commentary += f"{i}. {suggestion}\n"
    
    commentary += "\n---\n"
    commentary += "*（注：以上锐评纯属娱乐，如有雷同，纯属巧合）* 😏"
    
    return commentary

# 处理函数
def handle_tool_call(tool_name: str, params: Dict) -> str:
    """
    处理工具调用
    """
    if tool_name == "sharp_commentary_v2":
        address = params.get("address", "")
        return sharp_commentary_v2(address)
    else:
        return f"未知的工具: {tool_name}"

# 测试代码
if __name__ == "__main__":
    # 测试锐评功能
    test_address = "TM7S769qMobxfuvN73ASpyuwZUQS29JZmC"
    result = sharp_commentary_v2(test_address)
    print(result)