---
name: wallet-summary
description: Get comprehensive wallet overview including all token balances
version: 1.0.0
generated: true
author: AI Agent (Self-Generated)
tags: [auto-generated, blockchain, tron, wallet, balance]
---

# Wallet Summary

## When to use this skill

Use this skill when:
- User asks "查看钱包概况" or "wallet summary"
- User wants a quick overview of their holdings
- User needs to check multiple token balances at once

## Prerequisites

- Valid TRON network connection
- Wallet address (connected or provided)

## Features

1. Display all token balances (TRX, TRC20)
2. Show wallet address info
3. Network-aware (mainnet/nile testnet)

## How to use

### Basic Usage

```python
from personal_skills.wallet_summary.scripts.main import execute_skill

result = await execute_skill(
    address="TYourAddress...",
    network="nile"
)
print(result)
```

## Implementation Details

**Auto-Generated Information:**
- Created: 2026-02-08
- Based on user request: "查看钱包概况"
- Complexity: Low
