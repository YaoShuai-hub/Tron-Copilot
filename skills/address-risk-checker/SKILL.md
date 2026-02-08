---
name: address-risk-checker
description: Check TRON addresses for security risks using TronScan labels, blacklists, scam detection, and fraud transaction history before interacting.
---

# Address Risk Checker Skill

## When to use this skill

**CRITICAL**: Use this skill BEFORE any transaction to check if the recipient address is safe.

Use when:
- Before sending TRX or TRC20 tokens
- Before approving token allowances
- Before interacting with smart contracts
- User asks "Is this address safe?"
- Checking if an address is malicious/scam

## Security Checks Performed

### 1. 🚨 Blacklist Check
- Stablecoin blacklist (USDT/USDC)
- Known scam addresses
- Reported phishing addresses

### 2. ⚠️ Fraud Transaction Detection
- Account has engaged in fraudulent transactions
- Phishing transfer history
- Rug-pull deposit patterns

### 3. 🏷️ Address Labels
- TronScan public tags
- Project ownership verification
- Official/unofficial markers

### 4. 📊 Risk Score
- Activity patterns
- Transaction history analysis
- Relationship mapping with known bad actors

## API Integration

Uses TronScan Security API:
- Endpoint: `/api/account/security/{address}`
- Returns: blacklist status, fraud flags, labels
- Real-time data from TRON network

## Usage

```python
from skills.address_risk_checker.scripts.check_address import check_address_security

result = await check_address_security("TYourAddressHere...")
```

## Output Example

### ✅ Safe Address
```
✅ Address Security Check: SAFE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Address: TR7NHq...jLj6t
Status: ✅ Safe to interact

Checks:
  ✅ Not on blacklist
  ✅ No fraud transactions
  ✅ Verified: USDT Token Contract
  
Risk Level: LOW
```

### ⚠️ Risky Address
```
⚠️ Address Security Check: WARNING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Address: TBadAd...Scam
Status: ⚠️ HIGH RISK - DO NOT INTERACT

Risks Found:
  🚨 On stablecoin blacklist
  ⚠️ Fraud transactions detected
  ⚠️ Reported as scam
  
Risk Level: HIGH

🛑 RECOMMENDATION: DO NOT SEND FUNDS TO THIS ADDRESS
```

### ❌ Critical Risk
```
🚨 Address Security Check: DANGER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Address: TScamX...XXX
Status: 🚨 CRITICAL - CONFIRMED SCAM

Critical Issues:
  🚨 Confirmed scam address
  🚨 Multiple fraud reports
  🚨 Phishing activity detected
  🚨 On global blacklist
  
Risk Level: CRITICAL

🛑 STRONGLY RECOMMEND: CANCEL THIS TRANSACTION IMMEDIATELY
💡 This address has been flagged for malicious activity
```

## Integration with Transfer Skill

The transfer-tokens skill should AUTOMATICALLY call this checker:

```python
# Before building transfer transaction
risk_check = await check_address_security(to_address)

if risk_check['risk_level'] == 'CRITICAL':
    return "🚨 TRANSACTION BLOCKED: Recipient is confirmed scam address!"
elif risk_check['risk_level'] == 'HIGH':
    return "⚠️ WARNING: High risk address detected. Proceed with caution."
```

## Risk Levels

| Level | Description | Action |
|-------|-------------|--------|
| **SAFE** | No risks detected | ✅ Proceed |
| **LOW** | Minor warnings | ⚠️ Review warnings |
| **MEDIUM** | Multiple warning signs | ⚠️ Extra caution advised |
| **HIGH** | Known fraudulent activity | 🛑 Not recommended |
| **CRITICAL** | Confirmed scam/blacklisted | 🚨 Block transaction |

## Error Handling

- API timeout: Returns "UNKNOWN" with retry suggestion
- Invalid address: Returns format error
- Network issue: Fallback to basic format checks

## Important Notes

1. **Always run before transfers**: Even to "known" addresses
2. **Real-time data**: TronScan updates blacklists continuously
3. **Not 100% guarantee**: New scams may not be detected yet
4. **User education**: Explain why an address is risky

## Data Sources

- TronScan official blacklist
- Community reports
- On-chain behavior analysis
- TRON Foundation security alerts
- Stablecoin issuer blacklists (Tether, Circle)
