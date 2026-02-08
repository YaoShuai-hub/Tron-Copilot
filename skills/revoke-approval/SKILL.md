---
name: revoke-approval
description: Revoke risky token approvals to protect wallet security
version: 1.0.0
author: BlockChain-Copilot Team
tags: [security, approval, trc20, protection]
---

# Revoke Approval Skill

## When to use this skill

Use this skill to:
- **Revoke risky token approvals** identified by approval-scanner
- Cancel unlimited allowances to unknown contracts
- Clean up old/unused approvals
- Protect wallet from malicious contract exploits
- Complete the security audit loop: **Detect → Revoke**

## Why this matters

**Security Risk:** When you approve a contract (e.g., for swaps), you grant it permission to spend your tokens. If:
- Contract is compromised
- Approval is unlimited (`2^256-1`)
- Contract is no longer used

→ Your tokens are at risk! This skill revokes those permissions.

## How it works

```
User wallet
    ↓ Step 1
scanApprovals() → Find risky approvals
    ↓ Step 2
revokeApproval(contract, token) → Set allowance to 0
    ↓ Step 3
Transaction confirmed → Approval removed ✅
```

## Prerequisites

- Valid TRON wallet address
- Access to TronGrid API
- Target token contract address
- Spender contract address to revoke

## Usage

### Method 1: Revoke Specific Approval

```python
from skills.revoke_approval.scripts.revoke import build_revoke_transaction

# Revoke a specific approval
result = await build_revoke_transaction(
    owner_address="TYourAddress...",
    token_address="TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",  # USDT
    spender_address="TMaliciousContract..."
)

print(result['unsigned_tx'])  # Returns transaction to sign
```

### Method 2: Batch Revoke from Scanner Results

```python
# 1. Scan for risky approvals
from skills.approval_scanner.scripts.scan_approvals import scan_approvals

scan_result = await scan_approvals("TYourAddress...")

# 2. Revoke all critical risks
for risky in scan_result['risky_approvals']:
    tx = await build_revoke_transaction(
        owner_address="TYourAddress...",
        token_address=risky['token_address'],
        spender_address=risky['spender']
    )
    # Sign and broadcast tx
```

## Example Output

```json
{
  "success": true,
  "message": "Revoke approval transaction created successfully",
  "data": {
    "owner": "TYourAddress...",
    "token": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
    "token_symbol": "USDT",
    "spender": "TMaliciousContract...",
    "old_allowance": "115792089237316195423570985008687907853269984665640564039457584007913129639935",
    "new_allowance": "0",
    "unsigned_tx": {
      "txID": "...",
      "raw_data": {...},
      "visible": true
    },
    "estimated_energy": 15000,
    "estimated_bandwidth": 345
  },
  "warnings": [
    "⚠️ This will prevent the contract from spending your USDT",
    "You'll need to re-approve if you want to use this contract again"
  ]
}
```

## Security Flow Integration

**Complete Security Workflow:**

```
1. scan_approvals()          # Detect risks
   ↓
2. User reviews results       # Decision point
   ↓
3. revoke_approval()         # Take action
   ↓
4. Sign & broadcast          # Execute
   ↓
5. Wallet protected ✅
```

## Error Handling

Common errors and solutions:

### `NoApprovalFound`
```
Error: No approval found for this token/spender combination
Solution: Approval may have already been revoked or never existed
```

### `InsufficientEnergy`
```
Error: Not enough energy to execute transaction
Solution: Rent energy using energy-rental skill first
```

### `InvalidAddress`
```
Error: Token or spender address is invalid
Solution: Verify addresses are valid TRON addresses
```

## Implementation Details

**How revoke works:**
- Calls TRC20 `approve(spender, 0)` function
- Sets allowance to 0 (revokes permission)
- Returns unsigned transaction for user to sign

**Energy cost:** ~15,000 energy (~0.5 TRX or rent)

**Reversible:** Yes, you can re-approve anytime

## Integration with MCP

```python
# MCP tool wrapper
@mcp.tool()
async def revoke_token_approval(
    owner_address: str,
    token_address: str,
    spender_address: str
) -> str:
    """
    Revoke a token approval to protect wallet security.
    
    Args:
        owner_address: Your wallet address
        token_address: Token contract (e.g., USDT)
        spender_address: Contract to revoke approval from
    """
    result = await build_revoke_transaction(
        owner_address, token_address, spender_address
    )
    return format_for_agent(result)
```

## Best Practices

1. ✅ **Always scan first**: Use `approval-scanner` before revoking
2. ✅ **Verify contract**: Ensure you're revoking the right contract
3. ✅ **Batch wisely**: Revoke multiple approvals in sequence
4. ✅ **Save energy**: Rent energy if revoking many approvals
5. ⚠️ **Re-approval**: Remember to re-approve if you want to use the contract again

## Demo Script

**For hackathon presentation:**

```
User: "帮我检查钱包安全"

Agent:
1. [Calls approval-scanner]
   "发现3个风险授权：
    - SunSwap: 无限授权 USDT (1年前)
    - Unknown Contract: 无限授权 USDC (高风险)"

2. [Recommends action]
   "建议撤销这2个高风险授权"

3. User: "好的，撤销吧"

4. [Calls revoke-approval]
   "已生成撤销交易，请在钱包中签名确认"

5. [Transaction signed]
   "✅ 授权已撤销，钱包安全等级提升！"
```

This completes the **Data → Insight → Action** loop! 🔐

## Technical Notes

- Uses TronGrid `triggersmartcontract` endpoint
- Calls TRC20 standard `approve(address,uint256)` function
- Sets allowance to `0` to revoke
- Returns unsigned transaction (never touches private keys)
- Compatible with all TRC20 tokens

## See Also

- [Approval Scanner](../approval-scanner/SKILL.md) - Detect risky approvals
- [Token Security](../token-security/SKILL.md) - Verify token safety
- [Transfer Tokens](../transfer-tokens/SKILL.md) - Safe token transfers
