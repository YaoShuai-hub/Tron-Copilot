---
name: batch-transfer
description: Batch transfer TRX or TRC20 tokens to multiple addresses in one operation
version: 1.0.0
generated: true
author: AI Agent (Self-Generated)
tags: [auto-generated, blockchain, tron, batch, transfer]
---

# Batch Transfer

## When to use this skill

Use this skill when: 向10个地址批量转账TRX或TRC20代币

## Prerequisites

- Valid TRON network connection
- API keys configured in config.toml (if needed)
- Python 3.8+
- Sufficient balance to cover all transfers + fees

## Features

1. Support transferring to up to 100 addresses
2. Validate all addresses before execution
3. Calculate total amount and fees
4. Return detailed results for each transfer
5. Support both TRX and TRC20 tokens

## Data Sources

- TronGrid API (transaction building)
- Address validation utilities

## How to use

### Basic Usage

```python
from personal_skills.batch_transfer.scripts.main import execute_skill

# Execute the skill
result = await execute_skill(
    from_address="TYour...",
    recipients=[
        {"address": "TAddr1...", "amount": 10},
        {"address": "TAddr2...", "amount": 20},
        # ... more recipients
    ],
    token="TRX"  # or token contract address for TRC20
)

print(result)
```

### Example

```python
# Batch transfer 10 TRX to 10 different addresses
recipients = []
for i in range(10):
    recipients.append({
        "address": f"TTest{i}...",
        "amount": 10
    })

result = await execute_skill(
    from_address="TYourAddress...",
    recipients=recipients,
    token="TRX"
)

# Check results
if result['success']:
    print(f"Transferred to {result['data']['successful_count']} addresses")
    print(f"Total sent: {result['data']['total_amount']} TRX")
```

## Error Handling

Common errors and solutions:
- **ValidationError**: Check that all addresses are valid TRON addresses
- **InsufficientBalance**: Verify sender has enough balance for all transfers + fees
- **APIError**: Check network connection and API keys
- **RateLimitError**: Wait before retrying

## Limitations

This is an auto-generated skill. Limitations:
- Maximum 100 addresses per batch (recommended: 10-20 for better reliability)
- All transfers are executed sequentially (not atomic)
- If one transfer fails, remaining transfers are still attempted
- Requires manual signing of each transaction (security feature)

## Implementation Details

**Auto-Generated Information:**
- Created: 2026-02-08 04:15:10
- Based on user request: "向10个地址批量转账TRX或TRC20代币"
- Complexity: Medium

**Important**: This skill was automatically generated. Please review and test thoroughly before using in production.

## Next Steps

1. Review the generated code in `scripts/main.py`
2. Test with small amounts first (testnet recommended)
3. Refine error handling if needed
4. Update documentation with specific examples
5. Add unit tests

## Security Notes

⚠️ **IMPORTANT SECURITY WARNINGS:**
- Review each recipient address carefully before execution
- Start with small test amounts
- Use on testnet first
- Verify total amount + fees before confirming
- Keep private keys secure (never pass to this skill)

## References

For more information on Agent Skills format:
- See: `skills/skill-generator/references/ANTHROPIC_SKILLS_SPEC.md`
- Official docs: https://agentskills.io/
