"""
主交易系统
协调：数据获取 → AI 分析 → 风控 → 通知 → 人工确认 → 执行
配置来自 config/trading.yaml
"""

import logging
import time
from datetime import datetime, timedelta
from typing import List, Optional

from src.analyzer.minimax_client import MiniMaxClient
from src.config.loader import get_runtime_config
from src.core.models import SignalType, TradeSignal
from src.data.akshare_fetcher import fetch_realtime, get_stock_data, load_watchlist
from src.execution.paper_trader import PaperTrader
from src.notification.dingtalk import send_dingtalk
from src.notification.feishu import send_feishu
from src.risk.risk_engine import RiskEngine

logger = logging.getLogger(__name__)


class Notifier:
    """统一通知，webhook 来自 config/trading.yaml"""

    def __init__(self):
        rt = get_runtime_config()
        self.dingtalk = rt.get("dingtalk_webhook", "")
        self.feishu = rt.get("feishu_webhook", "")

    def send(self, signal: TradeSignal, action: str = "待确认", push_external: bool = True):
        emoji = {"buy": "🟢", "sell": "🔴", "hold": "⚪"}.get(signal.signal.value, "⚪")
        msg = f"""
{emoji} 【交易信号】{signal.symbol}

操作: {signal.signal.value.upper()}
置信度: {signal.confidence}/100
建议仓位: {signal.position_size:.0%}
状态: {action}

分析理由:
{signal.reason}

止损: {signal.stop_loss or '未设置'}
止盈: {signal.take_profit or '未设置'}

时间: {datetime.now().strftime("%H:%M:%S")}
"""
        if push_external:
            if self.dingtalk:
                send_dingtalk(self.dingtalk, msg.strip())
            if self.feishu:
                send_feishu(self.feishu, msg.strip())
        print(msg)


class TradingSystem:
    """主交易系统"""

    def __init__(self, provider: str = None):
        rt = get_runtime_config()
        self.mode = rt["trade_mode"]
        self.analyzer = MiniMaxClient(trade_mode=self.mode, provider=provider)
        self.risk_engine = RiskEngine()
        self.notifier = Notifier()
        self.paper_trader = PaperTrader(initial_capital=rt["initial_capital"])
        logger.info("交易系统初始化完成，交易模式: %s，投资模式: %s，模型: %s", self.mode, self.risk_engine.investment_mode, provider or "默认")

    def scan(
        self,
        watchlist: Optional[List[str]] = None,
        investment_mode: Optional[str] = None,
    ) -> List[TradeSignal]:
        """扫描自选股，返回通过风控的交易信号"""
        if watchlist is None:
            watchlist = load_watchlist()
        mode = investment_mode or self.risk_engine.investment_mode
        signals = []
        positions = self._get_position_weights()
        daily_pnl_pct = self._get_daily_pnl_pct()

        for symbol in watchlist:
            try:
                logger.info("分析 %s... (模式=%s)", symbol, mode)
                df, info, news, fund_flow, holder, valuation, sector, concept_hot, data_period, df_monthly, market_overview, sector_rank = get_stock_data(
                    symbol, investment_mode=mode
                )
                if df.empty:
                    logger.warning("%s 无数据", symbol)
                    continue

                signal = self.analyzer.analyze(
                    symbol, df, info, news,
                    fund_flow=fund_flow,
                    holder=holder,
                    valuation=valuation,
                    sector=sector,
                    concept_hot=concept_hot,
                    data_period=data_period,
                    df_monthly=df_monthly,
                    investment_mode=mode,
                    market_overview=market_overview,
                    sector_rank=sector_rank,
                )
                current_price = float(df.iloc[-1]["收盘"])
                passed, reason = self.risk_engine.check_signal(
                    signal, current_price, positions, daily_pnl_pct
                )
                if not passed:
                    logger.info("%s 未通过风控: %s", symbol, reason)

                # 记录信号历史（不论是否通过风控）
                self.paper_trader.save_signal(
                    signal, risk_passed=passed, risk_reason=reason,
                    investment_mode=mode,
                )

                # 置信度低也输出分析结果，供参考；DingTalk/Feishu 仅推送可执行信号
                is_actionable = passed and signal.signal != SignalType.HOLD and signal.confidence >= self.risk_engine.min_confidence * 100
                self.notifier.send(
                    signal,
                    "待确认" if is_actionable else "参考(未过风控/置信度不足)",
                    push_external=is_actionable,
                )

                # 仅将通过风控且置信度达标的 buy/sell 纳入可执行信号
                if is_actionable:
                    signals.append(signal)

                time.sleep(2)  # API 与数据源限流
            except Exception as e:
                logger.error("分析 %s 失败: %s", symbol, e)
        return signals

    def _get_position_weights(self) -> dict:
        """当前各标的仓位占比（使用市价）"""
        positions = self.paper_trader.get_positions()
        if not positions:
            return {}
        # 获取各持仓的当前市价
        prices = {}
        for pos in positions:
            rt = fetch_realtime(pos["symbol"])
            prices[pos["symbol"]] = rt.get("price", pos["cost"]) if rt else pos["cost"]
        pv = self.paper_trader.get_portfolio_value(prices)
        if pv <= 0:
            return {}
        weights = {}
        for pos in positions:
            price = prices.get(pos["symbol"], pos["cost"])
            mv = pos["quantity"] * price
            weights[pos["symbol"]] = mv / pv
        return weights

    def _get_daily_pnl_pct(self) -> float:
        """今日已实现盈亏占总资产比例"""
        pv = self.paper_trader.get_portfolio_value()
        if pv <= 0:
            return 0.0
        daily_pnl = self.paper_trader.get_daily_realized_pnl()
        return daily_pnl / pv

    def run_once(
        self,
        watchlist: Optional[List[str]] = None,
        investment_mode: Optional[str] = None,
    ):
        """运行一次：扫描 → 确认 → 执行"""
        mode = investment_mode or self.risk_engine.investment_mode
        logger.info("本次扫描: 模式=%s", mode)
        signals = self.scan(watchlist=watchlist, investment_mode=investment_mode)
        if not signals:
            logger.info("无交易信号")
            return

        confirmed = _batch_confirm(signals)
        for signal in confirmed:
            try:
                price_data = get_stock_data(signal.symbol, days=1, investment_mode="medium")
                df = price_data[0]  # 执行时仅需日线取价
                if df.empty:
                    continue
                price = float(df.iloc[-1]["收盘"])
                if self.mode == "paper":
                    self.paper_trader.execute(signal, price)
                else:
                    logger.warning("实盘模式未实现")
                self.notifier.send(signal, "已执行")
            except Exception as e:
                logger.error("执行失败 %s: %s", signal.symbol, e)

        status = self.paper_trader.get_status()
        logger.info(
            "账户: 现金=%.2f, 总市值=%.2f, 盈亏=%.2f",
            status["cash"],
            status["total_value"],
            status["pnl"],
        )

    def run_schedule(
        self,
        interval_minutes: int = 30,
        investment_mode: Optional[str] = None,
    ):
        """定时运行"""
        logger.info("启动定时交易，间隔 %d 分钟", interval_minutes)
        while True:
            try:
                self.run_once(investment_mode=investment_mode)
                next_run = datetime.now() + timedelta(minutes=interval_minutes)
                logger.info("下次运行: %s", next_run.strftime("%H:%M:%S"))
                time.sleep(interval_minutes * 60)
            except KeyboardInterrupt:
                logger.info("用户中断")
                break
            except Exception as e:
                logger.error("运行错误: %s", e)
                time.sleep(60)


def _batch_confirm(signals: List[TradeSignal]) -> List[TradeSignal]:
    """批量人工确认"""
    from src.ui.cli import confirm_signal

    confirmed = []
    for i, sig in enumerate(signals, 1):
        print(f"\n[{i}/{len(signals)}] ", end="")
        if confirm_signal(sig):
            confirmed.append(sig)
            print("✅ 已确认")
        else:
            print("❌ 已跳过")
    return confirmed
