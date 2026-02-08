#!/usr/bin/env python3
import json
import os
import time
import threading
from typing import Dict, Any

# 全局监控状态
monitor_state = {
    "running": False,
    "source_address": "TM7S769qMobxfuvN73ASpyuwZUQS29JZmC",
    "target_address": "TMP4FFPpKFDqMW99EdtjU8T8SrYfuANCZT",
    "last_balance": None,
    "thread": None
}

STATE_FILE = "monitor_trx_state.json"

def save_state():
    """保存状态到文件"""
    state = {
        "running": monitor_state["running"],
        "source_address": monitor_state["source_address"],
        "target_address": monitor_state["target_address"],
        "last_balance": monitor_state["last_balance"]
    }
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f)
    except Exception as e:
        print(f"保存状态失败: {e}")

def load_state():
    """从文件加载状态"""
    global monitor_state
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                monitor_state.update(state)
                print(f"已加载状态: {state}")
        except Exception as e:
            print(f"加载状态失败: {e}")

def monitor_loop():
    """监控循环"""
    try:
        from tronpy import Tron
        from tronpy.keys import PrivateKey
    except ImportError:
        print("错误: 需要安装 tronpy 库")
        print("请运行: pip install tronpy")
        monitor_state["running"] = False
        return
    
    source = monitor_state["source_address"]
    target = monitor_state["target_address"]
    
    print(f"开始监控 {source} -> {target}")
    
    # 获取私钥
    private_key_hex = os.getenv("TRON_PRIVATE_KEY")
    if not private_key_hex:
        print("错误: 未找到TRON_PRIVATE_KEY环境变量")
        monitor_state["running"] = False
        return
    
    client = Tron(network="mainnet")
    
    # 初始化余额
    try:
        account = client.get_account(source)
        initial_balance = account.get('balance', 0) / 1_000_000
        monitor_state["last_balance"] = initial_balance
        save_state()
        print(f"初始余额: {initial_balance} TRX")
    except Exception as e:
        print(f"获取初始余额失败: {e}")
        monitor_state["running"] = False
        return
    
    while monitor_state["running"]:
        try:
            # 获取当前余额
            account = client.get_account(source)
            current_balance = account.get('balance', 0) / 1_000_000
            last_balance = monitor_state["last_balance"]
            
            if current_balance > last_balance:
                increase = current_balance - last_balance
                print(f"\n💰 余额增加: {increase:.6f} TRX ({last_balance:.6f} -> {current_balance:.6f})")
                
                # 计算转账金额 (保留1 TRX作为手续费)
                transfer_amount = max(0, increase - 1.0)
                
                if transfer_amount > 0:
                    print(f"正在转账 {transfer_amount:.6f} TRX 到 {target}...")
                    
                    try:
                        priv_key = PrivateKey(bytes.fromhex(private_key_hex))
                        amount_sun = int(transfer_amount * 1_000_000)
                        
                        txn = (
                            client.trx.transfer(target, source, amount_sun)
                            .build()
                            .sign(priv_key)
                        )
                        
                        result = client.broadcast(txn)
                        
                        if result["result"]:
                            print(f"✅ 转账成功! TXID: {txn.txid}")
                            monitor_state["last_balance"] = current_balance - transfer_amount
                        else:
                            print(f"❌ 转账失败: {result}")
                            monitor_state["last_balance"] = current_balance
                    except Exception as e:
                        print(f"❌ 转账异常: {e}")
                        monitor_state["last_balance"] = current_balance
                else:
                    print(f"增加金额不足以支付手续费，跳过")
                    monitor_state["last_balance"] = current_balance
                
                save_state()
            elif current_balance < last_balance:
                print(f"📉 余额减少: {last_balance - current_balance:.6f} TRX")
                monitor_state["last_balance"] = current_balance
                save_state()
            
            time.sleep(10)
            
        except Exception as e:
            print(f"监控出错: {e}")
            time.sleep(30)

def start_monitor():
    """启动监控"""
    global monitor_state
    
    if monitor_state["running"]:
        return {
            "status": "already_running",
            "message": "监控已在运行",
            "source": monitor_state["source_address"],
            "target": monitor_state["target_address"],
            "last_balance": monitor_state["last_balance"]
        }
    
    load_state()
    monitor_state["running"] = True
    
    # 启动后台线程
    thread = threading.Thread(target=monitor_loop, daemon=True)
    monitor_state["thread"] = thread
    thread.start()
    
    return {
        "status": "started",
        "message": "监控已启动",
        "source": monitor_state["source_address"],
        "target": monitor_state["target_address"],
        "last_balance": monitor_state["last_balance"]
    }

def stop_monitor():
    """停止监控"""
    global monitor_state
    
    if not monitor_state["running"]:
        return {
            "status": "not_running",
            "message": "监控未运行"
        }
    
    monitor_state["running"] = False
    save_state()
    
    return {
        "status": "stopped",
        "message": "监控已停止",
        "last_balance": monitor_state["last_balance"]
    }

def get_status():
    """获取状态"""
    return {
        "running": monitor_state["running"],
        "source": monitor_state["source_address"],
        "target": monitor_state["target_address"],
        "last_balance": monitor_state["last_balance"],
        "has_thread": monitor_state["thread"] is not None
    }

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "start":
            result = start_monitor()
            print(json.dumps(result, indent=2))
            # 保持运行
            try:
                while monitor_state["running"]:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n收到中断信号，停止监控...")
                stop_monitor()
        elif cmd == "stop":
            result = stop_monitor()
            print(json.dumps(result, indent=2))
        elif cmd == "status":
            result = get_status()
            print(json.dumps(result, indent=2))
        else:
            print("用法: python start_monitor.py [start|stop|status]")
    else:
        result = start_monitor()
        print(json.dumps(result, indent=2))
        # 保持运行
        try:
            while monitor_state["running"]:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n收到中断信号，停止监控...")
            stop_monitor()
