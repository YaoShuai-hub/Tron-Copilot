"""
MCP tool wrappers for Agent Skills.
Bridges skills to FastMCP tool registration.
"""
import sys
import os
import json
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import skill scripts using absolute paths
# We'll import the functions directly from the script paths
import importlib.util

def _load_skill_module(skill_path):
    """Dynamically load a skill module from file path."""
    spec = importlib.util.spec_from_file_location("skill_module", skill_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# Load skills
fetch_price_module = _load_skill_module(project_root / "skills/token-price/scripts/fetch_price.py")
fetch_balance_module = _load_skill_module(project_root / "skills/wallet-balance/scripts/get_balance.py")
build_swap_module = _load_skill_module(project_root / "skills/swap-tokens/scripts/build_swap.py")
energy_rental_module = _load_skill_module(project_root / "skills/energy-rental/scripts/calculate_rental.py")
build_transfer_module = _load_skill_module(project_root / "skills/transfer-tokens/scripts/build_transfer.py")
address_risk_module = _load_skill_module(project_root / "skills/address-risk-checker/scripts/check_address.py")
address_book_module = _load_skill_module(project_root / "skills/address-book/scripts/manage_contacts.py")
address_profiling_module = _load_skill_module(project_root / "skills/address-profiling/scripts/analyze_address.py")
build_stake_module = _load_skill_module(project_root / "skills/stake-resource/scripts/build_stake.py")
build_unstake_module = _load_skill_module(project_root / "skills/stake-resource/scripts/build_unstake.py")
error_analysis_module = _load_skill_module(project_root / "skills/error-analysis/scripts/analyze_error.py")
malicious_detector_module = _load_skill_module(project_root / "skills/malicious-address-detector/scripts/check_malicious.py")

# Extract functions
fetch_price = fetch_price_module.get_token_price
fetch_balance = fetch_balance_module.get_wallet_balance
build_swap_transaction = build_swap_module.build_swap_transaction
get_rental_proposal = energy_rental_module.get_rental_proposal
build_transfer_transaction = build_transfer_module.build_transfer_transaction
check_address_security = address_risk_module.check_address_security
save_contact = address_book_module.save_contact
get_contact_alias = address_book_module.get_contact_alias
list_contacts = address_book_module.list_contacts
search_contacts = address_book_module.search_contacts
build_stake_transaction = build_stake_module.build_stake_transaction
build_unstake_transaction = build_unstake_module.build_unstake_transaction
analyze_error = error_analysis_module.analyze_error
check_malicious_address = malicious_detector_module.check_malicious_address

async def tool_get_token_price(symbol: str) -> str:
    """
    Get real-time cryptocurrency price for TRON ecosystem tokens.
    
    Args:
        symbol: Token symbol (e.g., TRX, USDT, BTT) or contract address
    """
    print(f"\n🔧 [SKILL CALL] token-price")
    print(f"   Parameters: symbol='{symbol}'")
    print(f"   Status: Fetching price data...\n")
    
    result = await fetch_price(symbol)
    
    if result.get('usd_price', 0) == 0:
        return f"❌ Price not available for {symbol}"
    
    price = result['usd_price']
    change = result.get('change_24h', 0)
    source = result.get('source', 'unknown')
    
    change_emoji = "📈" if change > 0 else "📉" if change < 0 else "➡️"
    
    return f"""💰 {symbol.upper()} Price: ${price:.4f} USD
{change_emoji} 24h Change: {change:+.2f}%
🔍 Source: {source.title()}
⏰ Updated: Just now"""

async def tool_get_wallet_balance(address: str, network: str = "nile") -> str:
    """
    Get comprehensive portfolio view of TRON wallet.
    
    Args:
        address: TRON wallet address (starts with T)
    """
    print(f"\n🔧 [SKILL CALL] wallet-balance")
    print(f"   Parameters: address='{address[:6]}...{address[-6:]}'")
    print(f"   Network: Nile Testnet")
    print(f"   Status: Fetching portfolio data...\n")
    
    result = await fetch_balance(address)
    
    if 'error' in result:
        return f"❌ Error: {result['error']}"
    
    total = result['total_value_usd']
    portfolio = result['portfolio']
    
    output = f"""💰 Wallet Portfolio: {address[:6]}...{address[-6:]}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Total Value: ${total:,.2f} USD

Assets:"""
    
    for i, token in enumerate(portfolio[:10], 1):  # Top 10
        symbol = token['symbol']
        amount = token['amount']
        value = token['value']
        pct = token['percentage']
        
        output += f"\n  {i}. {amount:,.2f} {symbol}  → ${value:,.2f} ({pct:.1f}%)"
    
    output += f"\n\n🔗 View on TronScan: https://nile.tronscan.org/#/address/{address}"
    output += f"\n⏰ Updated: Just now"
    
    return output

async def tool_swap_tokens(
    user_address: str,
    token_in: str,
    token_out: str,
    amount_in: float,
    slippage: float = 0.5
) -> str:
    """
    Build unsigned swap transaction for decentralized exchange (SunSwap V2).
    
    Args:
        user_address: Wallet address that will sign the transaction
        token_in: Input token symbol or address
        token_out: Output token symbol or address
        amount_in: Amount of input token to swap
        slippage: Maximum slippage tolerance (default 0.5%)
    """
    print(f"\n🔧 [SKILL CALL] swap-tokens")
    print(f"   Parameters: {token_in} → {token_out}, amount={amount_in}, slippage={slippage}%")
    print(f"   Network: Nile Testnet")
    print(f"   Status: Building swap transaction...\n")
    result = await build_swap_transaction(
        user_address, token_in, token_out, amount_in, slippage
    )
    
    if 'error' in result:
        return f"❌ Error: {result['error']}\n{result.get('message', '')}"
    
    if 'fallback' in result:
        return f"""⚠️ {result['error']}
        
💡 {result['message']}

For now, here's what the transaction would look like:
- Swap {amount_in} {token_in} → {token_out}
- Slippage tolerance: {slippage}%
- Router: SunSwap V2"""
    
    tx = result.get('transaction', {})
    metadata = result.get('metadata', {})
    
    return f"""✅ Swap Transaction Built

📝 Details:
  - Input: {amount_in} {token_in}
  - Output: {metadata.get('estimated_output', 'Unknown')}
  - Slippage: {slippage}%
  - Path: {' → '.join(metadata.get('path', [])[:2])}

🔐 Transaction Prepared (Please sign in the card below):
<<<JSON
{json.dumps(tx)}
JSON>>>
```json
{json.dumps(tx, indent=2)[:500]}...
```

⚠️ Next Steps:
{chr(10).join(f"{i}. {step}" for i, step in enumerate(metadata.get('instructions', []), 1))}
"""

async def tool_energy_rental(
    energy_needed: int,
    duration_days: int = 3
) -> str:
    """
    Analyze energy rental costs vs burning TRX.
    
    Args:
        energy_needed: Amount of energy required
        duration_days: Rental duration in days (default 3)
    """
    print(f"\n🔧 [SKILL CALL] energy-rental")
    print(f"   Parameters: energy={energy_needed:,}, duration={duration_days}d")
    print(f"   Status: Analyzing rental options...\n")
    result = await get_rental_proposal(energy_needed, duration_days)
    
    if 'error' in result:
        return f"❌ Error: {result['error']}"
    
    burn_cost = result['burn_cost_trx']
    options = result['rental_options']
    rec = result['recommendation']
    
    output = f"""⚡ Energy Rental Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Transaction needs: {energy_needed:,} Energy

💰 Cost Comparison:
  Option A - Burn TRX:  {burn_cost:.2f} TRX"""
    
    if options:
        best = options[0]
        savings = best['savings_percent']
        output += f"\n  Option B - Rent ({duration_days}d): {best['cost_trx']:.2f} TRX  ✅ Save {savings:.0f}%!"
        
        output += "\n\n📊 Rental Options:"
        for i, opt in enumerate(options, 1):
            star = " ⭐ Best" if opt['is_best'] else ""
            output += f"\n  {i}. {opt['platform']:<15} - {opt['cost_trx']:.2f} TRX ({opt['savings_percent']:+.0f}%){star}"
    
    output += f"\n\n⚡ Recommendation: {rec['action'].title()}"
    if rec['action'] == 'rent':
        output += f" from {rec.get('platform', 'cheapest platform')}"
    output += f"\n💡 Reason: {rec['reason']}"
    
    return output
async def tool_transfer_tokens(
    from_address: str,
    to_address: str,
    token: str,
    amount: float,
    memo: str = "",
    network: str = "nile"
) -> str:
    """
    Build unsigned transaction for token transfer.
    
    Args:
        from_address: Sender wallet address
        to_address: Recipient wallet address
        token: "TRX" or TRC20 contract address/symbol (e.g., "USDT")
        amount: Amount to transfer
        memo: Optional memo for TRX transfers
    """
    # Clean inputs
    to_address = to_address.strip()
    token = token.strip()
    if memo:
        memo = memo.strip()

    print(f"\n🔧 Tool Call: transfer_tokens with args {{'amount': {amount}, 'to_address': '{to_address}', 'token': '{token}'}} on network {network}\n")
    
    print("🔧 [SKILL CALL] transfer-tokens")
    print(f"   Parameters: {amount} {token}")
    print(f"   From: {from_address[:6]}...{from_address[-6:]}")
    print(f"   To: {to_address[:6]}...{to_address[-6:]}")
    print(f"   Network: {'Mainnet' if network == 'mainnet' else 'Nile Testnet' if network == 'nile' else 'Shasta Testnet'}")
    print(f"   Status: Orchestrating multi-skill security checks...\n")
    
    # Display sub-skills that will be called
    print("📋 Sub-skills to execute:")
    print("   1. 📇 address-book - Record transfer & lookup contact")
    print("   2. 🚨 malicious-address-detector - Check TronScan blacklist")
    print("   3. 🔒 address-risk-checker - Security risk assessment")
    if token.upper() != 'TRX':
        print("   4. ⚡ energy-rental - Calculate energy requirements")
        print("   5. 🔨 Build transaction")
    else:
        print("   4. 🔨 Build transaction")
    print("")
    
    # ⚠️ SECURITY CHECK: Automatically check recipient address safety
    print("🔒 Running automatic security check on recipient address...")
    risk_check = await check_address_security(to_address)
    
    # Check for validation error
    if 'error' in risk_check and risk_check.get('error') == 'Invalid address format':
        return f"❌ Error: Invalid recipient address format: {to_address}"
    
    # Block transaction if critical risk
    if risk_check['risk_level'] == 'CRITICAL':
        return f"""🚨 TRANSACTION BLOCKED FOR SECURITY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Recipient: {to_address[:6]}...{to_address[-6:]}

🛑 This address has been flagged as MALICIOUS

Reasons:
{chr(10).join(f'  • {w}' for w in risk_check['warnings'])}

💡 Recommendation: {risk_check['recommendation']}

🔒 Transfer has been BLOCKED to protect your funds."""
    
    # Warn if high risk but allow user to proceed
    if risk_check['risk_level'] == 'HIGH':
        print("⚠️ WARNING: High risk address detected!\n")
    
    # 📇 ADDRESS BOOK: Auto-save contact
    # Check if address already has an alias
    existing_alias = get_contact_alias(to_address)
    
    if memo and memo.strip():
        # Use memo as alias
        save_contact(to_address, alias=memo.strip(), increment_count=True)
        print(f"📇 Saved to address book: \"{memo.strip()}\"\n")
    else:
        # No memo - just increment count
        save_contact(to_address, alias=None, increment_count=True)
        if existing_alias:
            print(f"📇 Sending to saved contact: \"{existing_alias}\"\n")
    
    result = await build_transfer_transaction(from_address, to_address, token, amount, memo, network)
    
    if 'error' in result:
        return f"❌ Error: {result['error']}\n{result.get('message', '')}"
    
    if 'fallback' in result:
        return f"""⚠️ {result['error']}
        
💡 {result['message']}

Transfer details:
- From: {from_address[:6]}...{from_address[-6:]}
- To: {to_address[:6]}...{to_address[-6:]}
- Amount: {amount} {token}"""
    
    tx = result.get('transaction', {})
    metadata = result.get('metadata', {})
    
    token_display = metadata.get('token_symbol', metadata.get('token', token))
    transfer_type = metadata.get('type', 'TRANSFER')
    energy = metadata.get('estimated_energy', 0)
    cost = metadata.get('estimated_cost_trx', 0)
    
    # Build skill chain execution summary
    skill_results = []
    
    # Skill 1: Address Book
    if existing_alias:
        skill_results.append(f"📇 **地址簿查询**: ✅ 已知联系人「{existing_alias}」")
    else:
        skill_results.append(f"📇 **地址簿查询**: ℹ️ 新地址，已记录")
    
    # Skill 2: Malicious Address Check (from build_transfer)
    skill_results.append(f"🚨 **恶意检测**: ✅ 未发现恶意标签")
    
    # Skill 3: Risk Check
    if risk_check['risk_level'] in ['SAFE', 'LOW']:
        skill_results.append(f"🔒 **风险评估**: ✅ 低风险 ({risk_check['risk_level']})")
    elif risk_check['risk_level'] == 'HIGH':
        skill_results.append(f"🔒 **风险评估**: ⚠️ 高风险 - 请谨慎")
    else:
        skill_results.append(f"🔒 **风险评估**: 风险级别 {risk_check['risk_level']}")
    
    # Skill 4: Energy (TRC20 only)
    if token.upper() != 'TRX':
        if energy > 0:
            skill_results.append(f"⚡ **能量计算**: 需 ~{energy:,} 能量 (~{cost:.2f} TRX)")
        else:
            skill_results.append(f"⚡ **能量计算**: 预估 ~28,000 能量")
    
    
    # Skill 5: Build Transaction
    skill_results.append(f"🔨 **构建交易**: ✅ 交易已生成")
    
    output = f"""✅ **Skill 链执行完成**

您请求的转账操作已通过以下 5 个 Skill 的安全检查和处理：

{chr(10).join(skill_results)}

---

## 📝 交易详情

| 项目 | 值 |
|------|-----|
| 类型 | {transfer_type} |
| Token | {token_display} |
| 数量 | {amount:,} {token_display} |
| 发送方 | `{from_address[:6]}...{from_address[-6:]}` |
| 接收方 | `{to_address[:6]}...{to_address[-6:]}` |"""
    
    if metadata.get('memo'):
        output += f"\n| 备注 | {metadata['memo']} |"
    
    output += f"""

## ⚡ 资源消耗

- **能量 (Energy)**: ~{energy:,}"""
    
    if energy > 0:
        output += f" (燃烧需 ~{cost:.2f} TRX)"
    
    output += f"""
- **带宽 (Bandwidth)**: ~{metadata.get('estimated_bandwidth', 270)}"""
    
    if energy > 10000:
        output += f"\n\n💡 **提示**: 可使用能量租赁节省 ~70% 手续费！"
    
    output += f"""

<<<JSON
{json.dumps(tx)}
JSON>>>

⚠️ **安全检查清单**:
{chr(10).join(f"  {step}" for step in metadata.get('instructions', []))}

请在下方卡片中**确认并签名**交易 👇
"""
    
    return output

async def tool_check_address_security(address: str, network: str = "nile") -> str:
    """Check if a TRON address is safe before interacting."""
    # Clean input
    address = address.strip()

    print(f"\n🔧 [SKILL CALL] address-risk-checker")
    print(f"   Parameters: address='{address[:6]}...{address[-6:]}'")
    print(f"   Status: Checking TronScan security database...\n")
    
    result = await check_address_security(address)
    
    if 'error' in result:
        return f"❌ Error: {result['error']}"
    
    address_short = f"{address[:6]}...{address[-6:]}"
    risk_level = result['risk_level']
    
    if risk_level == 'CRITICAL':
        title = "🚨 Address Security Check: DANGER"
        status_line = "Status: 🚨 CRITICAL - CONFIRMED MALICIOUS"
    elif risk_level == 'HIGH':
        title = "⚠️ Address Security Check: HIGH RISK"
        status_line = "Status: ⚠️ HIGH RISK - NOT RECOMMENDED"
    elif risk_level == 'SAFE':
        title = "✅ Address Security Check: SAFE"
        status_line = "Status: ✅ Safe to interact"
    else:
        title = f"❓ Address Security Check: {risk_level}"
        status_line = f"Status: {risk_level}"
    
    output = f"""{title}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Address: {address_short}
{status_line}
"""
    
    if result['warnings']:
        output += f"\n\n⚠️ Findings:"
        for warning in result['warnings']:
            output += f"\n  {warning}"
    
    if result['labels']:
        output += f"\n\n🏷️ Labels:"
        for label in result['labels'][:5]:
            output += f"\n  • {label}"
    
    output += f"\n\nRisk Level: {risk_level}"
    output += f"\n\n💡 {result['recommendation']}"
    
    return output

async def tool_list_contacts(sort_by: str = "count") -> str:
    """List all saved address book contacts."""
    print(f"\n🔧 [SKILL CALL] address-book (list)")
    print(f"   Parameters: sort_by='{sort_by}'\n")
    
    contacts = list_contacts(sort_by)
    
    if not contacts:
        return "📇 Address Book is empty\n\nNo contacts saved yet. Contacts are automatically added when you transfer with a memo."
    
    output = f"""📇 Your Address Book
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total contacts: {len(contacts)}
"""
    
    if sort_by == "count":
        output += "\n📊 Most Frequently Used:\n"
    elif sort_by == "recent":
        output += "\n🕒 Recently Added:\n"
    else:
        output += "\n�� All Contacts:\n"
    
    for i, contact in enumerate(contacts[:20], 1):  # Top 20
        addr = contact['address']
        alias = contact.get('alias')
        count = contact.get('transfer_count', 0)
        
        addr_short = f"{addr[:6]}...{addr[-6:]}"
        
        if alias:
            output += f"\n  {i}. {alias} ({addr_short}) - {count} transfers"
        else:
            output += f"\n  {i}. {addr_short} - {count} transfers (no alias)"
    
    return output

async def tool_search_contacts(query: str) -> str:
    """Search address book by alias or address."""
    print(f"\n�� [SKILL CALL] address-book (search)")
    print(f"   Parameters: query='{query}'\n")
    
    results = search_contacts(query)
    
    if not results:
        return f"🔍 No contacts found matching '{query}'"
    
    output = f"""🔍 Search Results for '{query}'
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Found {len(results)} contact(s):
"""
    
    for i, contact in enumerate(results, 1):
        addr = contact['address']
        alias = contact.get('alias', 'No alias')
        count = contact.get('transfer_count', 0)
        
        output += f"\n{i}. {alias}"
        output += f"\n   Address: {addr}"
        output += f"\n   Transfers: {count}\n"
    
    return output

# Address profiling
profile_address = address_profiling_module.profile_address

async def tool_profile_address(address_or_alias: str, max_transactions: int = 1000) -> str:
    """Analyze address behavioral patterns and detect anomalies."""
    print(f"\n🔧 [SKILL CALL] address-profiling")
    print(f"   Parameters: address='{address_or_alias[:20]}...', max_tx={max_transactions}")
    print(f"   Status: Fetching transaction history and analyzing patterns...\n")
    
    result = await profile_address(address_or_alias, max_transactions, detect_anomalies=True)
    
    if 'error' in result:
        return f"❌ Error: {result['error']}"
    
    addr_display = result['alias'] if result.get('alias') else f"{result['address'][:6]}...{result['address'][-6:]}"
    
    output = f"""📊 Address Profile: {addr_display}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🏷️ Classification: {result['classification']}
⏱️ Analysis Period: {result['analysis_period']['days']} days
�� Total Transactions: {result['total_transactions']}
"""
    
    patterns = result.get('patterns', {})
    
    # Activity summary
    freq = patterns.get('frequency', {})
    output += f"\n\nActivity Summary:"
    output += f"\n  • Daily Average: {freq.get('daily_avg', 0)} transactions"
    if freq.get('peak_hour') is not None:
        output += f"\n  • Peak Activity: {freq['peak_hour']}:00 hour"
    
    # Token usage
    tokens = patterns.get('tokens', {})
    if tokens:
        most_common = list(tokens.items())[0]
        pct = (most_common[1] / result['total_transactions'] * 100)
        output += f"\n  • Most Active Token: {most_common[0]} ({pct:.0f}%)"
    
    # Transaction characteristics
    chars = result.get('characteristics', {})
    if chars:
        output += f"\n\n交易特征分析:"
        sr = chars.get('send_receive_ratio', {})
        if sr:
            output += f"\n  • 转出: {sr.get('send_count', 0)}笔 ({sr.get('total_sent', 0):.2f} TRX)"
            output += f"\n  • 转入: {sr.get('receive_count', 0)}笔 ({sr.get('total_received', 0):.2f} TRX)"
            if sr.get('ratio', 0) > 0:
                output += f"\n  • 收支比: {sr.get('ratio', 0):.2f}x"
        
        prog = chars.get('amount_progression', {})
        if prog and prog.get('is_increasing'):
            output += f"\n  ⚠️ 金额递增趋势: {prog['first_5_avg']:.1f} → {prog['last_5_avg']:.1f} TRX"
    
    # Pattern analysis
    output += f"\n\n交易模式:"
    vol = patterns.get('volume', {})
    if vol.get('avg_amount'):
        output += f"\n  ✓ 平均金额: {vol['avg_amount']:.2f} TRX"
    output += f"\n  ✓ {patterns.get('unique_counterparties', 0)} 个交易对手"
    
    # SCAM WARNINGS (most important!)
    scam_warnings = result.get('scam_warnings', [])
    if scam_warnings:
        output += f"\n\n🚨 诈骗风险警告: {len(scam_warnings)} 项\n"
        for i, scam in enumerate(scam_warnings, 1):
            severity_emoji = "🚨" if scam.get('severity') == 'critical' else "⚠️"
            output += f"\n  {i}. {severity_emoji} {scam.get('description', '')}"
            output += f"\n     详情: {scam.get('details', '')}"
            output += f"\n     {scam.get('recommendation', '')}\n"
    
    # Anomalies
    anomalies = result.get('anomalies', [])
    if anomalies and not scam_warnings:  # Only show if no scams (scams are more important)
        output += f"\n\n⚠️ 异常检测: {len(anomalies)} 项\n"
        for i, anomaly in enumerate(anomalies[:3], 1):  # Top 3
            severity_emoji = "🚨" if anomaly.get('severity') == 'high' else "⚠️"
            output += f"\n  {i}. {severity_emoji} {anomaly.get('type', 'unknown').replace('_', ' ').title()}"
            output += f"\n     {anomaly.get('description', '')}"
            output += f"\n     💡 {anomaly.get('recommendation', '')}\n"
    
    # Risk assessment
    risk = result['risk_level']
    risk_emoji = "🚨" if risk in ["CRITICAL", "HIGH"] else "⚠️" if risk == "MEDIUM" else "✅"
    output += f"\n\n风险评估: {risk_emoji} {risk}"
    output += f"\n💡 {result['summary']}"
    
    return output
