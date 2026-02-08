"""
Address behavioral profiling and anomaly detection.
Analyzes transaction history to identify patterns and unusual activity.
"""
import httpx
from src.config import Config
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import Counter
import statistics

# Import address book for alias resolution
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(project_root))

try:
    from skills.address_book.scripts.manage_contacts import get_contact_info, search_contacts
except:
    get_contact_info = None
    search_contacts = None

TRONSCAN_BASE = Config.TRONSCAN_BASE if hasattr(Config, 'TRONSCAN_BASE') else "https://nileapi.tronscan.org/api"

async def profile_address(
    address_or_alias: str,
    max_transactions: int = 1000,
    detect_anomalies: bool = True
) -> Dict:
    """
    Analyze address behavioral patterns from transaction history.
    
    Args:
        address_or_alias: TRON address or alias from address book
        max_transactions: Max number of transactions to analyze (default 1000)
        detect_anomalies: Whether to perform anomaly detection
        
    Returns:
        Dict with profile analysis and anomalies
    """
    # Step 1: Resolve alias to address
    address = await _resolve_address(address_or_alias)
    alias = None
    
    if address != address_or_alias:
        alias = address_or_alias  # User provided alias
    
    # Step 2: Fetch transaction history
    transactions = await _fetch_transaction_history(address, max_transactions)
    
    if not transactions:
        return {
            'address': address,
            'alias': alias,
            'error': 'No transaction history found',
            'total_transactions': 0
        }
    
    # Step 3: Analyze patterns
    patterns = _analyze_transaction_patterns(transactions)
    
    # Step 3.5: Analyze transaction characteristics (for scam detection)
    characteristics = _analyze_transaction_characteristics(transactions, address)
    
    # Step 4: Classify address behavior
    classification = _classify_address_behavior(patterns)
    
    # Step 5: Detect anomalies (if enabled)
    anomalies = []
    scam_warnings = []
    if detect_anomalies:
        anomalies = _detect_anomalies(transactions, patterns)
        # NEW: Detect scam patterns
        scam_warnings = _detect_scam_patterns(transactions, patterns, characteristics, address)
    
    # Step 6: Calculate risk assessment
    risk_level = _assess_risk(patterns, anomalies, scam_warnings)
    
    return {
        'address': address,
        'alias': alias,
        'total_transactions': len(transactions),
        'analysis_period': patterns.get('period'),
        'classification': classification,
        'patterns': patterns,
        'characteristics': characteristics,  # NEW
        'anomalies': anomalies,
        'scam_warnings': scam_warnings,  # NEW
        'risk_level': risk_level,
        'summary': _generate_summary(classification, patterns, anomalies, risk_level, scam_warnings)
    }

async def _resolve_address(address_or_alias: str) -> str:
    """Resolve alias to actual address using address book."""
    # If already looks like an address, return as-is
    if address_or_alias.startswith('T') and len(address_or_alias) == 34:
        return address_or_alias
    
    # Try to find in address book
    if get_contact_info:
        # Search for alias
        if search_contacts:
            results = search_contacts(address_or_alias)
            if results:
                return results[0]['address']
    
    # If not found, assume it's an address (might be invalid)
    return address_or_alias

async def _fetch_transaction_history(address: str, max_count: int) -> List[Dict]:
    """Fetch transaction history from TronScan API."""
    try:
        # Calculate time range (1 year ago)
        one_year_ago = int((datetime.now() - timedelta(days=365)).timestamp() * 1000)
        
        transactions = []
        start = 0
        limit = min(50, max_count)  # Fetch in batches
        
        headers = {}
        if Config.TRONSCAN_API_KEY:
            headers['TRON-PRO-API-KEY'] = Config.TRONSCAN_API_KEY
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            while len(transactions) < max_count:
                # Fetch transactions (both sent and received)
                url = f"{TRONSCAN_BASE}/transaction"
                params = {
                    'address': address,
                    'start': start,
                    'limit': limit,
                    'start_timestamp': one_year_ago,
                    'sort': '-timestamp'
                }
                
                response = await client.get(url, params=params, headers=headers)
                
                if response.status_code != 200:
                    break
                
                data = response.json()
                txs = data.get('data', [])
                
                if not txs:
                    break
                
                transactions.extend(txs)
                start += limit
                
                # Stop if we got less than requested (no more data)
                if len(txs) < limit:
                    break
        
        return transactions[:max_count]
    
    except Exception as e:
        print(f"Error fetching transactions: {e}")
        return []

def _analyze_transaction_patterns(transactions: List[Dict]) -> Dict:
    """Analyze transaction patterns."""
    if not transactions:
        return {}
    
    # Extract key metrics
    timestamps = []
    amounts = []
    directions = {'sent': 0, 'received': 0}
    tokens = Counter()
    counterparties = set()
    hours_of_day = Counter()
    
    for tx in transactions:
        # Timestamp
        ts = tx.get('timestamp', 0) / 1000  # Convert to seconds
        timestamps.append(ts)
        
        # Hour of day
        hour = datetime.fromtimestamp(ts).hour
        hours_of_day[hour] += 1
        
        # Amount (simplified - would need token-specific parsing)
        amount = tx.get('amount', 0)
        try:
            amount_value = float(amount) if amount else 0
            if amount_value > 0:
                amounts.append(amount_value / 1_000_000)  # Convert from SUN
        except (ValueError, TypeError):
            pass  # Skip invalid amounts
        
        # Direction
        # This is simplified - real implementation would check owner_address
        if tx.get('toAddress'):
            directions['sent'] += 1
        if tx.get('fromAddress'):
            directions['received'] += 1
        
        # Tokens
        token = tx.get('tokenInfo', {}).get('tokenAbbr', 'TRX')
        tokens[token] += 1
        
        # Counterparties (simplified)
        if tx.get('toAddress'):
            counterparties.add(tx.get('toAddress'))
        if tx.get('fromAddress'):
            counterparties.add(tx.get('fromAddress'))
    
    # Calculate patterns
    if timestamps:
        time_range_days = (max(timestamps) - min(timestamps)) / 86400
        daily_avg = len(transactions) / max(time_range_days, 1)
        
        # Peak activity hour
        peak_hour = hours_of_day.most_common(1)[0][0] if hours_of_day else None
    else:
        time_range_days = 0
        daily_avg = 0
        peak_hour = None
    
    # Amount statistics
    if amounts:
        avg_amount = statistics.mean(amounts)
        median_amount = statistics.median(amounts)
        max_amount = max(amounts)
        amount_stdev = statistics.stdev(amounts) if len(amounts) > 1 else 0
    else:
        avg_amount = median_amount = max_amount = amount_stdev = 0
    
    # Most common token
    most_common_token = tokens.most_common(1)[0] if tokens else ('Unknown', 0)
    
    return {
        'period': {
            'start': datetime.fromtimestamp(min(timestamps)).isoformat() if timestamps else None,
            'end': datetime.fromtimestamp(max(timestamps)).isoformat() if timestamps else None,
            'days': int(time_range_days)
        },
        'frequency': {
            'daily_avg': round(daily_avg, 2),
            'peak_hour': peak_hour
        },
        'volume': {
            'avg_amount': round(avg_amount, 2),
            'median_amount': round(median_amount, 2),
            'max_amount': round(max_amount, 2),
            'stdev': round(amount_stdev, 2)
        },
        'direction': directions,
        'tokens': dict(tokens.most_common(3)),
        'unique_counterparties': len(counterparties)
    }

def _classify_address_behavior(patterns: Dict) -> str:
    """Classify address behavior type."""
    if not patterns:
        return "Unknown"
    
    daily_avg = patterns.get('frequency', {}).get('daily_avg', 0)
    unique_counterparties = patterns.get('unique_counterparties', 0)
    
    # Classification logic
    if daily_avg > 10:
        if unique_counterparties > 50:
            return "Exchange / High-Frequency Trader"
        else:
            return "Active Trader / Bot"
    elif daily_avg > 2:
        return "Active User"
    elif daily_avg > 0.5:
        return "Regular User"
    elif daily_avg > 0.1:
        return "Occasional User"
    else:
        return "Inactive / Holder"

def _detect_anomalies(transactions: List[Dict], patterns: Dict) -> List[Dict]:
    """Detect anomalous behavior."""
    anomalies = []
    
    if not transactions or not patterns:
        return anomalies
    
    # Get baseline metrics
    avg_amount = patterns.get('volume', {}).get('avg_amount', 0)
    stdev = patterns.get('volume', {}).get('stdev', 0)
    
    # Anomaly 1: Large amount spike (>3 standard deviations)
    for tx in transactions[:10]:  # Check recent 10
        amount = tx.get('amount', 0)
        try:
            amount_value = float(amount) / 1_000_000 if amount else 0
            if stdev > 0 and amount_value > avg_amount + (3 * stdev):
                anomalies.append({
                    'type': 'large_transfer_spike',
                    'severity': 'high',
                    'description': f"Unusually large transfer: {amount_value:.2f} (avg: {avg_amount:.2f})",
                    'timestamp': datetime.fromtimestamp(tx.get('timestamp', 0) / 1000).strftime('%Y-%m-%d'),
                    'recommendation': 'Verify this transaction was intentional'
                })
        except (ValueError, TypeError):
            pass
    
    # Anomaly 2: Sudden frequency spike (simplified)
    # Would need time-series analysis for proper implementation
    
    # Anomaly 3: Dormancy awakening
    if len(transactions) > 1:
        latest = transactions[0].get('timestamp', 0) / 1000
        second_latest = transactions[1].get('timestamp', 0) / 1000
        gap_days = (latest - second_latest) / 86400
        
        if gap_days > 90:  # More than 3 months gap
            anomalies.append({
                'type': 'dormancy_awakening',
                'severity': 'medium',
                'description': f'Address was inactive for {int(gap_days)} days before recent activity',
                'recommendation': 'Check if account was compromised'
            })
    
    return anomalies

def _assess_risk(patterns: Dict, anomalies: List[Dict]) -> str:
    """Assess overall risk level."""
    if not anomalies:
        return "LOW"
    
    high_severity = sum(1 for a in anomalies if a.get('severity') == 'high')
    medium_severity = sum(1 for a in anomalies if a.get('severity') == 'medium')
    
    if high_severity >= 2:
        return "HIGH"
    elif high_severity >= 1:
        return "MEDIUM"
    elif medium_severity >= 2:
        return "MEDIUM"
    else:
        return "LOW"

def _generate_summary(classification: str, patterns: Dict, anomalies: List[Dict], risk_level: str) -> str:
    """Generate human-readable summary."""
    if not patterns:
        return "Insufficient data for analysis"
    
    daily_avg = patterns.get('frequency', {}).get('daily_avg', 0)
    
    summary = f"This address is classified as '{classification}' with daily average of {daily_avg:.1f} transactions. "
    
    if anomalies:
        summary += f"{len(anomalies)} anomal{'y' if len(anomalies) == 1 else 'ies'} detected. "
    else:
        summary += "No unusual patterns detected. "
    
    summary += f"Overall risk: {risk_level}."
    
    return summary

def _analyze_transaction_characteristics(transactions: List[Dict], target_address: str) -> Dict:
    """Analyze transaction characteristics to detect scam patterns."""
    characteristics = {
        'send_receive_ratio': {},
        'amount_progression': [],
        'counterparty_analysis': {},
        'return_pattern': None
    }
    
    if not transactions:
        return characteristics
    
    # Analyze send vs receive with amounts
    sends = []
    receives = []
    
    for tx in transactions:
        amount = tx.get('amount', 0)
        try:
            amount_value = float(amount) / 1_000_000 if amount else 0
        except (ValueError, TypeError):
            continue
        
        # Check if this address sent or received (simplified)
        owner = tx.get('ownerAddress', '')
        to_addr = tx.get('toAddress', '')
        
        if owner == target_address:
            sends.append(amount_value)
        if to_addr == target_address:
            receives.append(amount_value)
    
    # Calculate send/receive ratio
    total_sent = sum(sends) if sends else 0
    total_received = sum(receives) if receives else 0
    
    characteristics['send_receive_ratio'] = {
        'total_sent': round(total_sent, 2),
        'total_received': round(total_received, 2),
        'ratio': round(total_received / total_sent, 2) if total_sent > 0 else 0,
        'send_count': len(sends),
        'receive_count': len(receives)
    }
    
    # Analyze amount progression (are amounts increasing?)
    if sends:
        characteristics['amount_progression'] = {
            'first_5_avg': round(sum(sends[:5]) / min(5, len(sends)), 2),
            'last_5_avg': round(sum(sends[-5:]) / min(5, len(sends)), 2),
            'is_increasing': sum(sends[-5:]) > sum(sends[:5]) if len(sends) >= 10 else False
        }
    
    # Check for "return pattern" (small amounts returned initially)
    if sends and receives and len(sends) >= 3 and len(receives) >= 2:
        early_sends = sends[:3]
        early_receives = receives[:2]
        
        # If early receives > early sends (returning more than sent)
        if sum(early_receives) > sum(early_sends):
            characteristics['return_pattern'] = {
                'type': 'early_return_bait',
                'early_return_ratio': round(sum(early_receives) / sum(early_sends), 2),
                'warning': 'Address initially returned more than sent (possible bait)'
            }
    
    return characteristics

def _detect_scam_patterns(
    transactions: List[Dict],
    patterns: Dict,
    characteristics: Dict,
    address: str
) -> List[Dict]:
    """Detect common scam patterns."""
    scams = []
    
    # Pattern 1: Bait-and-Switch Investment Scam
    # Small amounts returned initially, then stops returning
    return_pattern = characteristics.get('return_pattern')
    if return_pattern and return_pattern.get('type') == 'early_return_bait':
        ratio = return_pattern.get('early_return_ratio', 0)
        if ratio > 1.1:  # Returning >110% initially
            scams.append({
                'type': 'bait_and_switch_investment',
                'severity': 'critical',
                'description': f'⚠️ 诱导投资骗局特征: 初期返利{ratio:.1f}倍，吸引大额投入',
                'details': '前几次小额投资返利超过本金，建立信任后收到大额投资不返还',
                'recommendation': '🚨 高度警惕！这是典型的"杀猪盘"骗局模式，切勿继续投入'
            })
    
    # Pattern 2: One-way flow (only receives, never sends back)
    sr_ratio = characteristics.get('send_receive_ratio', {})
    if sr_ratio.get('receive_count', 0) > 10 and sr_ratio.get('send_count', 0) == 0:
        scams.append({
            'type': 'money_sink',
            'severity': 'high',
            'description': f'⚠️ 只进不出: 收到{sr_ratio["receive_count"]}笔转账，从未转出',
            'details': '地址只接收资金，从不发送，可能是诈骗收款地址或已跑路项目',
            'recommendation': '🛑 极高风险！资金很可能无法收回'
        })
    
    # Pattern 3: Honeypot (receives much more than sends)
    if sr_ratio.get('ratio', 0) > 10:  # Receives 10x more than sends
        scams.append({
            'type': 'honeypot_suspicious',
            'severity': 'high',
            'description': f'⚠️ 资金黑洞: 收入是支出的{sr_ratio["ratio"]:.1f}倍',
            'details': '地址接收资金远超转出，资金集中不流动',
            'recommendation': '🚨 警告：可能是资金盘或蜜罐合约'
        })
    
    # Pattern 4: Increasing investment amounts (victim being baited)
    prog = characteristics.get('amount_progression', {})
    if prog.get('is_increasing'):
        if prog['last_5_avg'] > prog['first_5_avg'] * 5:  # 5x increase
            scams.append({
                'type': 'escalating_investment',
                'severity': 'medium',
                'description': f'⚠️ 投资金额递增: {prog["first_5_avg"]:.1f} → {prog["last_5_avg"]:.1f} TRX',
                'details': '用户投入金额持续增加，符合被骗局诱导的模式',
                'recommendation': '⚠️ 建议停止继续投入，谨防"沉没成本陷阱"'
            })
    
    # Pattern 5: Suspicious small equal amounts (testing or dusting attack)
    if transactions:
        recent_amounts = []
        for tx in transactions[:20]:
            try:
                amt = float(tx.get('amount', 0)) / 1_000_000
                recent_amounts.append(amt)
            except:
                pass
        
        # Check if many transactions have same small amount
        if recent_amounts:
            from collections import Counter
            amt_counts = Counter([round(a, 1) for a in recent_amounts if a < 10])
            most_common = amt_counts.most_common(1)
            if most_common and most_common[0][1] >= 5:  # Same amount 5+ times
                scams.append({
                    'type': 'dusting_or_testing',
                    'severity': 'low',
                    'description': f'⚠️ 重复小额交易: {most_common[0][1]}笔相同金额({most_common[0][0]} TRX)',
                    'details': '可能是撒网式测试或"粉尘攻击"',
                    'recommendation': 'ℹ️ 注意：可能在寻找活跃钱包进行后续诈骗'
                })
    
    return scams

def _assess_risk(patterns: Dict, anomalies: List[Dict], scam_warnings: List[Dict] = None) -> str:
    """Assess overall risk level including scam detection."""
    if scam_warnings is None:
        scam_warnings = []
    
    # Critical if any scam pattern detected
    critical_scams = sum(1 for s in scam_warnings if s.get('severity') == 'critical')
    high_scams = sum(1 for s in scam_warnings if s.get('severity') == 'high')
    
    if critical_scams >= 1:
        return "CRITICAL"
    
    if high_scams >= 1:
        return "HIGH"
    
    # Original anomaly-based assessment
    high_severity = sum(1 for a in anomalies if a.get('severity') == 'high')
    medium_severity = sum(1 for a in anomalies if a.get('severity') == 'medium')
    
    if high_severity >= 2:
        return "HIGH"
    elif high_severity >= 1 or scam_warnings:
        return "MEDIUM"
    elif medium_severity >= 2:
        return "MEDIUM"
    else:
        return "LOW"

def _generate_summary(
    classification: str,
    patterns: Dict,
    anomalies: List[Dict],
    risk_level: str,
    scam_warnings: List[Dict] = None
) -> str:
    """Generate human-readable summary including scam warnings."""
    if not patterns:
        return "Insufficient data for analysis"
    
    if scam_warnings is None:
        scam_warnings = []
    
    daily_avg = patterns.get('frequency', {}).get('daily_avg', 0)
    
    summary = f"This address is classified as '{classification}' with daily average of {daily_avg:.1f} transactions. "
    
    if scam_warnings:
        summary += f"🚨 {len(scam_warnings)} SCAM PATTERN(S) DETECTED! "
    elif anomalies:
        summary += f"{len(anomalies)} anomal{'y' if len(anomalies) == 1 else 'ies'} detected. "
    else:
        summary += "No unusual patterns detected. "
    
    summary += f"Overall risk: {risk_level}."
    
    return summary
