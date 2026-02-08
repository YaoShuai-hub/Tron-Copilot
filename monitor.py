"""Simple periodic monitors for on-chain and position alerts."""

from __future__ import annotations

import argparse
import time

from tron_mcp.modules import onchain_monitor, risk_monitor


def _sleep(seconds: int) -> None:
    try:
        time.sleep(seconds)
    except KeyboardInterrupt:
        raise SystemExit(0)


def run_onchain(interval: int, notify: bool, broadcast: bool, rules_path: str | None, log_audit: bool) -> None:
    while True:
        try:
            onchain_monitor.onchain_alerts(
                notify=notify, broadcast=broadcast, rules_path=rules_path, log_audit=log_audit
            )
        except Exception as err:  # noqa: BLE001
            print(f"[onchain] error: {err}")
        _sleep(interval)


def run_position(
    exchange_id: str,
    interval: int,
    notify: bool,
    broadcast: bool,
    rules_path: str | None,
) -> None:
    while True:
        try:
            risk_monitor.position_alerts(
                exchange_id=exchange_id,
                notify=notify,
                broadcast=broadcast,
                rules_path=rules_path,
            )
        except Exception as err:  # noqa: BLE001
            print(f"[position] error: {err}")
        _sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run periodic monitors.")
    parser.add_argument("--mode", choices=["onchain", "position", "all"], default="onchain")
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--exchange-id", dest="exchange_id", default=None)
    parser.add_argument("--notify", action="store_true")
    parser.add_argument("--broadcast", action="store_true")
    parser.add_argument("--onchain-rules", dest="onchain_rules", default=None)
    parser.add_argument("--risk-rules", dest="risk_rules", default=None)
    parser.add_argument("--audit", dest="log_audit", action="store_true")
    args = parser.parse_args()

    if args.mode in {"position", "all"} and not args.exchange_id:
        raise SystemExit("exchange-id is required for position monitoring")

    if args.mode == "onchain":
        run_onchain(args.interval, args.notify, args.broadcast, args.onchain_rules, args.log_audit)
    elif args.mode == "position":
        run_position(args.exchange_id, args.interval, args.notify, args.broadcast, args.risk_rules)
    else:
        while True:
            try:
                onchain_monitor.onchain_alerts(
                    notify=args.notify,
                    broadcast=args.broadcast,
                    rules_path=args.onchain_rules,
                    log_audit=args.log_audit,
                )
            except Exception as err:  # noqa: BLE001
                print(f"[onchain] error: {err}")
            try:
                risk_monitor.position_alerts(
                    exchange_id=args.exchange_id,
                    notify=args.notify,
                    broadcast=args.broadcast,
                    rules_path=args.risk_rules,
                )
            except Exception as err:  # noqa: BLE001
                print(f"[position] error: {err}")
            _sleep(args.interval)


if __name__ == "__main__":
    main()
