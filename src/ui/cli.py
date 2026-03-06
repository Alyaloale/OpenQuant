"""
命令行交互
确认交易: y/n/d/s
"""

import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from src.config.loader import get_model_config, get_runtime_config
from src.core.models import TradeSignal
from src.core.trading_system import TradingSystem
from src.data.akshare_fetcher import (
    add_to_watchlist,
    fetch_realtime,
    get_stock_pool,
    load_watchlist,
)

# 日志（统一路径）
from src.config.paths import get_log_dir, ensure_dirs
ensure_dirs()
LOG_DIR = get_log_dir()
daily_dir = LOG_DIR / datetime.now().strftime("%Y%m%d")
daily_dir.mkdir(parents=True, exist_ok=True)
log_file = daily_dir / "trading.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def confirm_signal(signal: TradeSignal) -> bool:
    """等待用户确认单个信号"""
    print("\n" + "=" * 60)
    print(f"【交易确认】{signal.symbol}")
    print("=" * 60)
    print(f"信号: {signal.signal.value.upper()}")
    print(f"置信度: {signal.confidence}/100")
    print(f"建议仓位: {signal.position_size:.0%}")
    print(f"止损: {signal.stop_loss}")
    print(f"止盈: {signal.take_profit}")
    print(f"\n分析理由:\n{signal.reason}")
    print("=" * 60)

    while True:
        choice = input("\n确认执行? [y/n/d(详情)/s(跳过)]: ").strip().lower()
        if choice == "y":
            return True
        if choice in ("n", "s"):
            return False
        if choice == "d":
            print("\n--- 原始API响应 ---")
            print(signal.raw_response[:2000])
            print("---\n")
        else:
            print("请输入 y/n/d/s")


def run_scan(symbols: str = None, mode: str = None, model: str = None) -> int:
    """单次扫描自选股"""
    provider = model or "minimax"
    if not get_model_config(provider).get("api_key"):
        print(f"错误: 未设置 API Key，请在 config/model.yaml 的 {provider}.api_key 中配置")
        return 1

    watchlist = None
    if symbols:
        watchlist = [s.strip() for s in symbols.split(",") if s.strip()]

    system = TradingSystem(provider=model)
    print(f"扫描模式: {mode or 'medium'}" + (f"，模型: {model}" if model else ""))
    system.run_once(watchlist=watchlist, investment_mode=mode)
    return 0


def run_scheduler(interval: int = 30, mode: str = None, model: str = None) -> int:
    """定时扫描模式"""
    provider = model or "minimax"
    if not get_model_config(provider).get("api_key"):
        print(f"错误: 未设置 API Key，请在 config/model.yaml 的 {provider}.api_key 中配置")
        return 1
    system = TradingSystem(provider=model)
    system.run_schedule(interval_minutes=interval, investment_mode=mode)
    return 0


def show_status() -> int:
    """展示持仓与盈亏"""
    from src.execution.paper_trader import PaperTrader

    initial = get_runtime_config()["initial_capital"]
    trader = PaperTrader(initial_capital=initial)
    status = trader.get_status()
    print("\n=== 账户状态 ===")
    print(f"现金: {status['cash']:.2f}")
    print(f"总市值: {status['total_value']:.2f}")
    print(f"盈亏: {status['pnl']:.2f}")
    print("\n持仓:")
    for pos in status["positions"]:
        p = status["positions"][pos]
        print(f"  {pos}: {p['quantity']} 股 @ {p['cost']:.2f}")
    return 0


def generate_report(period: str = "day") -> int:
    """生成复盘报告"""
    from src.execution.paper_trader import PaperTrader

    initial = get_runtime_config()["initial_capital"]
    trader = PaperTrader(initial_capital=initial)
    status = trader.get_status()
    print(f"\n=== {period} 复盘报告 ===")
    print(f"总盈亏: {status['pnl']:.2f} ({status['pnl']/initial*100:.2f}%)")
    print(f"今日交易次数: {status['trades_today']}")
    return 0


def run_pick(pool: str = "hot", limit: int = 20, add: bool = False, mode: str = None, model: str = None) -> int:
    """AI 选股：从股池中筛选并可选加入自选"""
    provider = model or "minimax"
    if not get_model_config(provider).get("api_key"):
        print(f"错误: 未设置 API Key，请在 config/model.yaml 的 {provider}.api_key 中配置")
        return 1
    symbols = get_stock_pool(source=pool, limit=limit)
    print(f"\n从 {pool} 股池选取 {len(symbols)} 只，扫描模式: {mode or 'medium'}" + (f"，模型: {model}" if model else ""))
    system = TradingSystem(provider=model)
    signals = system.scan(watchlist=symbols, investment_mode=mode)
    if not signals:
        print("无符合条件标的")
        return 0
    print(f"\n共 {len(signals)} 个信号")
    for i, sig in enumerate(signals, 1):
        print(f"  {i}. {sig.symbol} {sig.signal.value} 置信度{sig.confidence}")
    if add and signals:
        choice = input("\n将上述标的加入自选? [y/n]: ").strip().lower()
        if choice == "y":
            for sig in signals:
                if add_to_watchlist(sig.symbol):
                    print(f"  已加入 {sig.symbol}")
    return 0


def run_watch(symbols: str = None, interval: int = 10) -> int:
    """实时监控股价 + 持仓盈亏 + 止损止盈告警"""
    from src.execution.paper_trader import PaperTrader
    from src.risk.risk_engine import RiskEngine

    watch = symbols.split(",") if symbols else load_watchlist()
    watch = [s.strip() for s in watch if s.strip()]

    initial = get_runtime_config()["initial_capital"]
    trader = PaperTrader(initial_capital=initial)
    risk = RiskEngine()
    positions = {p["symbol"]: p for p in trader.get_positions()}

    # 合并自选股和持仓股
    all_symbols = list(dict.fromkeys(watch + list(positions.keys())))

    print(f"\n监控 {all_symbols}，每 {interval} 秒刷新 (Ctrl+C 退出)")
    if positions:
        print(f"持仓: {list(positions.keys())}")

    try:
        while True:
            print(f"\n--- {datetime.now().strftime('%H:%M:%S')} ---")
            for sym in all_symbols:
                d = fetch_realtime(sym)
                if not d:
                    print(f"  {sym}: 无数据")
                    continue

                price = d.get("price", 0)
                src = d.get("source", "")
                pct = d.get("change_pct")
                line = f"  {sym}: {price:.2f}"
                if pct is not None:
                    line += f" ({pct:+.2f}%)"
                line += f" [{src}]"

                # 持仓盈亏显示
                if sym in positions:
                    pos = positions[sym]
                    cost = pos.get("cost", 0)
                    qty = pos.get("quantity", 0)
                    if cost > 0:
                        pnl = (price - cost) * qty
                        pnl_pct = (price / cost - 1) * 100
                        line += f"  💰 {qty}股 成本{cost:.2f} 盈亏{pnl:+.2f}({pnl_pct:+.1f}%)"

                print(line)

                # 止损止盈告警
                if sym in positions:
                    alerts = risk.check_position_alerts(positions[sym], price)
                    for alert in alerts:
                        if alert["type"] == "stop_loss":
                            print(f"    🚨 止损告警: {alert['reason']}")
                        elif alert["type"] == "take_profit":
                            print(f"    🎯 止盈告警: {alert['reason']}")

            # 显示账户汇总
            if positions:
                prices_map = {}
                for sym in positions:
                    d = fetch_realtime(sym)
                    if d:
                        prices_map[sym] = d.get("price", positions[sym].get("cost", 0))
                pv = trader.get_portfolio_value(prices_map)
                total_pnl = pv - initial
                print(f"  ── 账户: 总市值 {pv:.2f}  盈亏 {total_pnl:+.2f} ({total_pnl/initial*100:+.1f}%)")

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n已停止")
    return 0


def show_history(limit: int = 20, symbol: str = None) -> int:
    """显示信号历史记录"""
    from src.execution.paper_trader import PaperTrader

    initial = get_runtime_config()["initial_capital"]
    trader = PaperTrader(initial_capital=initial)
    records = trader.get_signal_history(limit=limit, symbol=symbol)
    if not records:
        print("暂无信号记录")
        return 0
    print(f"\n=== 信号历史 (最近 {len(records)} 条) ===")
    for r in records:
        emoji = {"buy": "🟢", "sell": "🔴", "hold": "⚪"}.get(r.get("signal", ""), "⚪")
        passed = "✅" if r.get("risk_passed") else "❌"
        t = r.get("time", "")[:16]
        print(
            f"  {t} {emoji} {r['symbol']} {r['signal'].upper():4s} "
            f"置信{r['confidence']:3.0f} 仓位{r.get('position_size', 0):.0%} "
            f"风控{passed} [{r.get('investment_mode', '')}]"
        )
        if r.get("reason"):
            # 截取理由前80字符
            reason = r["reason"][:80].replace("\n", " ")
            print(f"    {reason}...")
        if not r.get("risk_passed") and r.get("risk_reason"):
            print(f"    风控原因: {r['risk_reason']}")
    return 0


def run_watchlist_add(symbol: str) -> int:
    """添加自选"""
    if add_to_watchlist(symbol):
        print(f"已添加 {symbol} 到自选")
    else:
        print(f"{symbol} 已在自选列表中")
    return 0


def run_watchlist_remove(symbol: str) -> int:
    """移除自选"""
    from src.data.akshare_fetcher import remove_from_watchlist

    if remove_from_watchlist(symbol):
        print(f"已从自选移除 {symbol}")
    else:
        print(f"{symbol} 不在自选列表中")
    return 0


def run_watchlist_show() -> int:
    """显示自选列表"""
    symbols = load_watchlist()
    print("\n当前自选股:")
    for s in symbols:
        print(f"  {s}")
    return 0
