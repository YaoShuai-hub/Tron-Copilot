---
name: address-profiling
description: Analyze address behavior patterns from transaction history. Detect anomalies, identify activity patterns, and alert on suspicious changes.
---

# Address Profiling Skill

## When to use this skill

Use this skill to:
- Analyze an address's transaction behavior patterns
- Detect unusual activity (frequency spikes, large transfers, new counterparties)
- Profile addresses before interacting (is this a normal user or bot?)
- Monitor saved contacts for behavioral changes
- Get insights: "Is this address actively trading or just holding?"

## Analysis Performed

### 📊 Transaction Pattern Analysis
- **Frequency**: Transactions per day/week/month
- **Volume**: Average/median/max transfer amounts
- **Direction**: Ratio of sent vs received
- **Active hours**: Time-of-day patterns
- **Regularity**: Consistent patterns vs sporadic activity

### 🔍 Anomaly Detection
- **Sudden spikes** in transaction frequency
- **Unusual amounts** (outliers from normal range)
- **New counterparties** (never interacted before)
- **Time anomalies** (activity at unusual hours)
- **Dormant awakening** (long inactive then sudden activity)

### 🏷️ Address Classification
- **Exchange deposit**: Regular small deposits
- **Whale**: Large holdings, infrequent large transfers
- **Active trader**: High-frequency swaps
- **Smart contract**: Automated patterns
- **Normal user**: Varied, human-like behavior
- **Possible bot**: Highly regular patterns

## Usage

### Basic Profiling
```python
from skills.address_profiling.scripts.analyze_address import profile_address

result = await profile_address("TXXXabc...")
# Or use alias from address book:
result = await profile_address("妈妈")
```

### With Time Range
```python
result = await profile_address(
    address="TXXXabc...",
    max_transactions=1000,  # Last 1000 txs or 1 year
    detect_anomalies=True
)
```

## Output Example

```
📊 Address Profile: 妈妈 (TXXXabc...abc)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🏷️ Classification: Active Trader
⏱️ Analysis Period: 2025-02-08 to 2026-02-08 (365 days)
📈 Total Transactions: 847

Activity Summary:
  • Daily Average: 2.3 transactions
  • Peak Activity: 15:00-18:00 UTC+8
  • Most Active Token: USDT (67%)
  
Transaction Patterns:
  ✓ Regular activity (no long gaps)
  ✓ Consistent amounts ($50-$500 range)
  ✓ 15 unique counterparties
  
⚠️ Anomalies Detected: 2

  1. 🚨 Large Transfer Spike (2026-02-01)
     Sent 5,000 USDT (10x normal amount)
     Recommendation: Verify this was intentional
     
  2. ⚠️ New Counterparty (2026-02-05)
     First interaction with TYYYnew...
     Recommendation: Check counterparty security

Risk Assessment: LOW
💡 This address shows normal user behavior with occasional
   large transfers. Recent activity aligns with patterns.
```

## Integration with Address Book

Automatically resolves aliases:
```
User: "分析一下妈妈这个地址的交易情况"
Agent: Looks up "妈妈" → TXXXabc... → Profiles address
```

## Data Sources

- **TronScan API**: Transaction history
- **TronGrid**: Block timestamps
- **Address Book**: Alias resolution

## Privacy

- ⚠️ Only analyzes public blockchain data
- 🔒 Analysis results stored locally (optional)
- ✅ No private information required
