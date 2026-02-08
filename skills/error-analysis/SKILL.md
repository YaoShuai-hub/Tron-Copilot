---
name: error-analysis
description: Analyze TRON blockchain transaction errors using AI to provide concise, user-friendly explanations with root causes and actionable solutions.
---

# Error Analysis Skill

## When to use this skill

Use this skill when:
- A transaction fails with a cryptic error message
- User asks "为什么报错？" or "怎么解决？"
- Need to explain blockchain errors in simple terms
- Transaction broadcast returns error codes

## What it does

Analyzes TRON blockchain errors and provides:
1. **Root cause** - Simple explanation in one sentence
2. **Possible reasons** - 2 main contributing factors
3. **Solutions** - 2 actionable steps to fix the issue

Output is **extremely concise** (< 100 characters total).

## Common errors handled

| Error Message | Meaning | Solution |
|--------------|---------|----------|
| `balance is not sufficient` | TRX balance too low | Top up TRX |
| `Contract validate error` | Energy/bandwidth shortage | Stake or rent energy |
| `account not found` | Account not activated | Send 1 TRX to activate |
| `Transaction expired` | TX took too long | Retry transaction |
| `REVERT opcode` | Smart contract execution failed | Check contract parameters |

## How to use

```python
from skills.error_analysis.scripts.analyze_error import analyze_error

result = await analyze_error(
    error_message="Contract validate error : No contract or Not enough energy",
    error_context="broadcast"  # Optional: "transfer", "signing", "broadcast"
)

# Returns:
# {
#     "analysis": "TRX余额不足支付手续费",
#     "causes": ["未质押获取能量", "账户余额 < 手续费"],
#     "suggestions": ["充值 TRX", "质押获取能量"]
# }
```

## Output format

**Concise format** (< 100 chars):
```
原因：TRX余额不足
1. 未质押获取能量
2. 账户余额 < 手续费
建议：
1. 充值 TRX
2. 质押获取能量
```

## Hex decoding

Automatically decodes hex-encoded error messages:
- Detects hex format (e.g., `436f6e747261637420...`)
- Converts to human-readable text
- Analyzes decoded message

## Error context types

- `transfer` - Error during transfer preparation
- `signing` - Error during wallet signing
- `broadcast` - Error during network broadcast
- `validation` - Error during transaction validation

## LLM prompt design

Uses optimized prompt for brevity:
- Total output < 100 Chinese characters
- No redundant explanations
- Direct problem → solution mapping
- Leverages TRON-specific error patterns

## Integration

Skill is called by:
1. **API endpoint**: `/api/analyze-error` (current)
2. **LLM tool** (future): `analyze_error` function
3. **Frontend**: TransactionCard error handler

## Performance

- Response time: < 2 seconds
- Token usage: ~150 tokens per analysis
- Caching: Not implemented (errors are unique)
