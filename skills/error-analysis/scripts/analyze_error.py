"""
Error Analysis Skill for TRON Blockchain

Analyzes transaction and blockchain errors using AI to provide:
- Concise root cause explanation
- Top 2 contributing factors
- Top 2 actionable solutions

Total output < 100 Chinese characters for maximum clarity.
"""

import sys
import json
from pathlib import Path
from typing import Dict, Optional

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import Config


def decode_hex_error(error_message: str) -> str:
    """
    Decode hex-encoded error messages.
    
    TRON sometimes returns errors in hex format. This function detects
    and decodes them automatically.
    
    Args:
        error_message: Potential hex-encoded error string
        
    Returns:
        Decoded error message (or original if not hex)
    """
    # Check if looks like hex (starts with '43' which is 'C' in ASCII)
    if error_message.startswith('43') and len(error_message) > 50:
        try:
            decoded = bytes.fromhex(error_message).decode('utf-8', errors='ignore')
            # Only return decoded if it looks valid
            if decoded.isprintable():
                return decoded
        except (ValueError, UnicodeDecodeError):
            pass
    
    return error_message


def parse_llm_response(text: str) -> Dict[str, any]:
    """
    Parse LLM response into structured format.
    
    Expected format:
        原因：[explanation]
        1. [cause 1]
        2. [cause 2]
        建议：
        1. [suggestion 1]
        2. [suggestion 2]
    
    Args:
        text: LLM response text
        
    Returns:
        Dict with 'analysis', 'causes', 'suggestions'
    """
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    analysis = ""
    causes = []
    suggestions = []
    current_section = None
    
    for line in lines:
        # Check for section headers
        if '原因' in line and ('：' in line or ':' in line):
            current_section = 'analysis'
            # Extract analysis after colon
            if '：' in line:
                analysis = line.split('：', 1)[-1].strip()
            elif ':' in line:
                analysis = line.split(':', 1)[-1].strip()
        elif '建议' in line or 'suggestion' in line.lower():
            current_section = 'suggestions'
        # Check for numbered/bulleted items
        elif line[0].isdigit() or line.startswith(('-', '•', '*')):
            clean = line.lstrip('0123456789.-•* ').strip()
            if current_section == 'suggestions':
                suggestions.append(clean)
            elif current_section == 'analysis':
                causes.append(clean)
            else:
                # Default to causes if unclear
                causes.append(clean)
    
    # Fallback values
    if not analysis and lines:
        analysis = lines[0][:100]
    if not causes:
        causes = ['交易执行失败', '请查看详细日志']
    if not suggestions:
        suggestions = ['检查余额和资源', '稍后重试']
    
    return {
        'analysis': analysis[:100],  # Enforce length limit
        'causes': causes[:2],  # Top 2 only
        'suggestions': suggestions[:2]  # Top 2 only
    }


async def analyze_error(
    error_message: str,
    error_context: Optional[str] = None
) -> Dict[str, any]:
    """
    Analyze blockchain error with AI.
    
    Args:
        error_message: Error message to analyze (hex or plain text)
        error_context: Optional context ('transfer', 'broadcast', 'signing')
        
    Returns:
        {
            'analysis': str,  # Root cause (< 100 chars)
            'causes': List[str],  # Top 2 reasons
            'suggestions': List[str]  # Top 2 solutions
        }
    """
    # Import AI client (lazy import to avoid circular dependency)
    try:
        from src.server import ai_client
    except ImportError:
        return {
            'analysis': '错误分析服务不可用',
            'causes': ['AI 服务未配置'],
            'suggestions': ['检查 config.toml', '重启后端服务']
        }
    
    if not ai_client:
        return {
            'analysis': 'AI 客户端未初始化',
            'causes': ['配置文件可能有误'],
            'suggestions': ['检查 API key', '查看启动日志']
        }
    
    try:
        # Decode hex if needed
        decoded_error = decode_hex_error(error_message)
        
        # Build context string
        context_info = f"\n场景: {error_context}" if error_context else ""
        
        # Call LLM with optimized prompt
        response = await ai_client.chat.completions.create(
            model=Config.AI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": """你是TRON专家。用户遇到错误，提供超简洁分析。

要求：
- 总字数 < 100
- 直接说原因，不重复错误信息
- 2个主要原因
- 2个解决方案

格式：
原因：[一句话]
1. [原因1]
2. [原因2]
建议：
1. [方案1]
2. [方案2]

常见错误：
- balance not sufficient = TRX不足
- Contract validate = 能量/带宽不足
- account not found = 账户未激活
- REVERT = 合约执行失败"""
                },
                {
                    "role": "user",
                    "content": f"错误: {decoded_error}{context_info}"
                }
            ],
            temperature=0.3,
            max_tokens=200
        )
        
        # Parse response
        llm_text = response.choices[0].message.content or "无法分析错误"
        return parse_llm_response(llm_text)
        
    except Exception as e:
        print(f"[ERROR] Error analysis failed: {e}", file=sys.stderr)
        return {
            'analysis': f'分析失败: {str(e)[:50]}',
            'causes': ['服务异常', 'LLM 调用失败'],
            'suggestions': ['查看完整错误', '联系技术支持']
        }


# CLI interface for testing
if __name__ == '__main__':
    import asyncio
    
    try:
        # Read parameters from stdin
        input_data = sys.stdin.read().strip()
        
        if not input_data:
            print(json.dumps({
                'error': 'No input provided',
                'usage': 'echo \'{"error_message": "...", "error_context": "..."}\' | python analyze_error.py'
            }, ensure_ascii=False, indent=2))
            sys.exit(1)
        
        params = json.loads(input_data)
        error_msg = params.get('error_message', '')
        context = params.get('error_context')
        
        if not error_msg:
            print(json.dumps({
                'error': 'error_message is required'
            }, ensure_ascii=False, indent=2))
            sys.exit(1)
        
        # Run analysis
        result = asyncio.run(analyze_error(error_msg, context))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
    except json.JSONDecodeError as e:
        print(json.dumps({
            'error': f'Invalid JSON input: {str(e)}'
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({
            'error': f'Unexpected error: {str(e)}'
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)
