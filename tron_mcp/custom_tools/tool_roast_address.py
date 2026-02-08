"""
锐评地址工具 - 查找地址最近交易记录并进行锐评分析
"""
from typing import Dict, Any, List
import json

TOOL_DEFINITIONS = [
    {
        "name": "roast_address",
        "description": "锐评TRON地址的交易行为 - 查找最近交易记录并进行讽刺性锐评分析",
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

def call_tool(tool_name: str, params: Dict[str, Any]) -> str:
    """
    调用工具的主函数
    """
    if tool_name == "roast_address":
        return roast_address(params)
    else:
        return f"未知的工具: {tool_name}"

def roast_address(params: Dict[str, Any]) -> str:
    """
    锐评地址的主函数
    """
    from tron_mcp.tools import get_recent_transactions, roast_address_transactions
    
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
    
    # 检查是否有交易记录
    if isinstance(transactions, dict) and transactions.get("total") == 0:
        return f"🔍 地址分析结果\n\n地址: {address}\n\n💭 锐评：\n\n这个地址看起来是个"区块链隐士"！\n\n没有任何交易记录，就像是刚创建的账号，或者是个一直默默囤币的hodler。也许是在等待某个重大时机，也许只是忘记了私钥... 😅\n\n建议：\n- 检查是否还有私钥访问权限\n- 考虑是否需要激活这个地址\n- 或者继续保持神秘感！"
    
    # 进行锐评分析
    try:
        roast_result = roast_address_transactions()
        roast_data = json.loads(roast_result)
    except Exception as e:
        return f"交易记录获取成功，但锐评分析失败: {str(e)}\n\n交易记录: {json.dumps(transactions, ensure_ascii=False, indent=2)}"
    
    # 组合结果
    output = f"🔍 地址锐评分析结果\n\n"
    output += f"📍 分析地址: {address}\n"
    output += f"📊 交易记录数: {len(transactions.get('data', []))} 条\n\n"
    
    if "roast" in roast_data:
        output += f"💭 锐评分析:\n\n{roast_data['roast']}\n"
    
    if "summary" in roast_data:
        output += f"\n📈 交易概览:\n{roast_data['summary']}\n"
    
    if "patterns" in roast_data:
        output += f"\n🔍 交易模式:\n{roast_data['patterns']}\n"
    
    if "risk_level" in roast_data:
        output += f"\n⚠️ 风险等级: {roast_data['risk_level']}\n"
    
    return output

# 测试用例
if __name__ == "__main__":
    # 测试工具定义
可以通过以下方式调用：
    test_params = {
        "address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzg3Lk3J",  # USDT合约地址作为示例
        "limit": 10
    }
    result = roast_address(test_params)
    print(result)