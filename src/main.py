"""
OpenQuant 入口程序
支持: 单次扫描、定时模式、状态查询、报告生成
"""

import argparse
import sys
from pathlib import Path

# 添加项目根目录到 path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 配置已迁移至 config/model.yaml 和 config/trading.yaml


def main():
    parser = argparse.ArgumentParser(
        description="OpenQuant - AI 半自动量化交易系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # scan: 单次扫描
    scan_parser = subparsers.add_parser("scan", help="单次扫描自选股")
    scan_parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="指定股票代码，逗号分隔，如 000001,600519",
    )
    scan_parser.add_argument(
        "--mode",
        type=str,
        choices=["short", "medium", "long"],
        default=None,
        help="投资模式: short(短线)/medium(中线)/long(长线)，默认用 config/trading.yaml",
    )
    scan_parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="AI 模型: minimax/deepseek，默认用 config/model.yaml",
    )

    # run: 定时模式
    run_parser = subparsers.add_parser("run", help="启动定时扫描模式")
    run_parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="扫描间隔(分钟)，默认30",
    )
    run_parser.add_argument(
        "--mode",
        type=str,
        choices=["short", "medium", "long"],
        default=None,
        help="投资模式: short/medium/long",
    )
    run_parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="AI 模型: minimax/deepseek",
    )

    # status: 查看持仓
    subparsers.add_parser("status", help="查看当前持仓和盈亏")

    # report: 复盘报告
    report_parser = subparsers.add_parser("report", help="生成复盘报告")
    report_parser.add_argument(
        "--period",
        type=str,
        choices=["day", "week", "month"],
        default="day",
        help="报告周期",
    )

    # pick: AI 选股
    pick_parser = subparsers.add_parser("pick", help="AI 选股（从人气榜等股池筛选）")
    pick_parser.add_argument("--pool", default="hot", help="股池: hot/watchlist")
    pick_parser.add_argument("--limit", type=int, default=20, help="分析数量")
    pick_parser.add_argument("--add", action="store_true", help="将选中标的加入自选")
    pick_parser.add_argument(
        "--mode",
        type=str,
        choices=["short", "medium", "long"],
        default=None,
        help="投资模式: short/medium/long",
    )
    pick_parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="AI 模型: minimax/deepseek",
    )

    # watch: 实时监控
    watch_parser = subparsers.add_parser("watch", help="实时监控股价（轮询，有延迟）")
    watch_parser.add_argument("--symbols", type=str, help="股票代码逗号分隔，默认自选股")
    watch_parser.add_argument("--interval", type=int, default=10, help="刷新间隔(秒)")

    # watchlist: 自选股管理
    wl_parser = subparsers.add_parser("watchlist", help="自选股管理")
    wl_sub = wl_parser.add_subparsers(dest="wl_cmd")
    wl_sub.add_parser("list", help="显示自选")
    add_p = wl_sub.add_parser("add", help="添加")
    add_p.add_argument("symbol", help="股票代码")
    rm_p = wl_sub.add_parser("remove", help="移除")
    rm_p.add_argument("symbol", help="股票代码")

    # history: 信号历史
    hist_parser = subparsers.add_parser("history", help="查看 AI 分析信号历史")
    hist_parser.add_argument("--limit", type=int, default=20, help="显示条数")
    hist_parser.add_argument("--symbol", type=str, default=None, help="按股票代码筛选")

    # test: 运行测试
    subparsers.add_parser("test", help="运行测试套件")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "scan":
        from src.ui.cli import run_scan
        return run_scan(symbols=args.symbols, mode=getattr(args, "mode", None), model=getattr(args, "model", None))

    elif args.command == "run":
        from src.ui.cli import run_scheduler
        return run_scheduler(interval=args.interval, mode=getattr(args, "mode", None), model=getattr(args, "model", None))

    elif args.command == "status":
        from src.ui.cli import show_status
        return show_status()

    elif args.command == "report":
        from src.ui.cli import generate_report
        return generate_report(period=args.period)

    elif args.command == "pick":
        from src.ui.cli import run_pick
        return run_pick(pool=args.pool, limit=args.limit, add=args.add, mode=getattr(args, "mode", None), model=getattr(args, "model", None))

    elif args.command == "watch":
        from src.ui.cli import run_watch
        return run_watch(symbols=args.symbols, interval=args.interval)

    elif args.command == "history":
        from src.ui.cli import show_history
        return show_history(limit=args.limit, symbol=args.symbol)

    elif args.command == "watchlist":
        from src.ui.cli import (
            run_watchlist_add,
            run_watchlist_remove,
            run_watchlist_show,
        )
        wl_cmd = getattr(args, "wl_cmd", None)
        if wl_cmd == "list" or wl_cmd is None:
            return run_watchlist_show()
        if wl_cmd == "add":
            return run_watchlist_add(args.symbol)
        if wl_cmd == "remove":
            return run_watchlist_remove(args.symbol)

    elif args.command == "test":
        import subprocess
        return subprocess.call([sys.executable, "-m", "pytest", "tests/", "-v"])

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
