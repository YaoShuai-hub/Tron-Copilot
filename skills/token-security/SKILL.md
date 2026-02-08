---
name: token-security
description: Analyze token contract security (honeypot, rug-pull risks, liquidity locks). Essential before trading.
---

# Token Security Analyzer

## When to use this skill

Use this skill **BEFORE**:
- Buying a new token
- Adding liquidity to a pool
- Approving token contracts
- Investing in unknown projects

## Security Checks Performed

### 🔴 Critical Risks

**1. Honeypot Detection**
- Can you sell after buying?
- Hidden sell taxes >50%
- Blacklist functions
- **If detected: DO NOT BUY!**

**2. Rug Pull Indicators**
- Owner can mint unlimited tokens
- Owner can change tax to 100%
- Owner can pause trading
- No liquidity lock

**3. Malicious Code**
- Hidden backdoors
- Proxy contracts (can change logic)
- Self-destruct functions

### ⚠️ Medium Risks

**4. High Taxes**
- Buy tax >10%
- Sell tax >15%
- Combined tax >20%

**5. Ownership Centralization**
- Single owner (not renounced)
- No multi-sig
- Can change critical parameters

**6. Liquidity Risks**
- Low liquidity (<$10K)
- No liquidity lock
- Owner holds LP tokens

### ✅ Good Signs

- Contract verified on TronScan
- Ownership renounced
- Liquidity locked
- Reasonable taxes (<5%)
- Audit report available

## Usage

```python
from skills.token_security.scripts.analyze_token import analyze_token_security

# Check token before trading
result = await analyze_token_security("TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t")

# Get risk score
risk = result['risk_level']  # SAFE, LOW, MEDIUM, HIGH, CRITICAL
```

## Output Example

```
🔐 Token Security Analysis: SCAM_TOKEN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Contract: TXXXabc...
Verified: ❌ NOT VERIFIED

🚨 CRITICAL RISKS DETECTED: 3

  1. 🚫 HONEYPOT DETECTED
     Cannot sell after buying
     Sell function has hidden revert
     
  2. 🚨 Owner Can Mint Unlimited Tokens
     Risk: Instant rug pull possible
     
  3. ⚠️ No Liquidity Lock
     Owner can remove all liquidity anytime

⚠️ MEDIUM RISKS: 2

  4. High Sell Tax: 25%
  5. Single Owner (not renounced)

Risk Score: 🚨 CRITICAL - DO NOT TRADE

💡 Verdict: This token shows multiple signs of a scam.
    Probability of rug pull: >90%
    AVOID AT ALL COSTS!
```

## Integration

Should automatically run when:
- User tries to swap for unknown token
- User adds token to balance tracker
- User asks about a token

## Data Sources

- **TronScan**: Contract verification, source code
- **Token Sniffer**: Honeypot detection API
- **Go+ Security**: Token security data
- **Contract Analysis**: Bytecode analysis for malicious patterns
