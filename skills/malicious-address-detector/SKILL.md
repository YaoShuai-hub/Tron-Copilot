---
name: malicious-address-detector
description: Detect malicious TRON addresses using TronScan's official tag/label database to identify scam, phishing, and fraudulent addresses.
---

# Malicious Address Detector Skill

## When to use this skill

**CRITICAL**: Use this skill BEFORE any transfer to detect scam addresses.

Use when:
- Before sending any TRX/TRC20 tokens
- User asks "Is this a scam address?"
- Validating recipient addresses in transfers
- Checking addresses from unknown sources

## What it does

Checks TronScan's official tag database for malicious labels:
- 🚨 **Scam** - Confirmed scam address
- ⚠️ **Phishing** - Phishing attack address
- ⚠️ **Fake** - Impersonation address
- ⚠️ **Mixer** - Privacy mixer/tumbler
- ⚠️ **Gambling** - Gambling contract

## TronScan API Integration

**Endpoint**: 
```
https://apilist.tronscanapi.com/api/account/tokens?address={address}
```

**Response includes**:
- `tags`: Array of labels (e.g., ["Scam", "Phishing"])
- `name`: Address name if labeled
- Verified status

## Usage

```python
from skills.malicious_address_detector.scripts.check_malicious import check_malicious_address

result = await check_malicious_address("TYourAddress...")
# Returns:
# {
#   "is_malicious": true,
#   "risk_level": "DANGER",
#   "tags": ["Scam", "Phishing"],
#   "warnings": ["⚠️ Address tagged as Scam on TronScan"],
#   "source": "tronscan"
# }
```

## Risk Levels

| Level | Tags | Action |
|-------|------|--------|
| **SAFE** | No malicious tags | ✅ Proceed |
| **WARNING** | Mixer, Gambling | ⚠️ Caution advised |
| **DANGER** | Scam, Phishing, Fake | 🚨 Block transaction |

## Output Format

**Safe Address**:
```
✅ No malicious tags detected
Source: TronScan
```

**Malicious Address**:
```
🚨 DANGER: Address tagged as malicious on TronScan
Tags: Scam, Phishing
⚠️ DO NOT send funds to this address!
```

## Integration with Transfer

Called automatically in transfer flow:
```python
# In transfer-tokens skill
malicious_check = await check_malicious_address(to_address)
if malicious_check['is_malicious']:
    raise Error(f"🚨 {malicious_check['warnings'][0]}")
```

## Caching

- Cache duration: 5 minutes
- Reduces API calls for repeated checks
- Cache key: `malicious:{address}`

## Error Handling

- API timeout → Return SAFE with warning
- Invalid address → Return format error
- Network error → Fallback to UNKNOWN

## Limitations

- Only detects TronScan-labeled addresses
- New scams may not be tagged yet
- False negatives possible
- Not a replacement for user diligence
