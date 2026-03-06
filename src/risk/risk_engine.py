"""
风控引擎
本地硬规则：仓位 / 止损 / 单日风控
"""

import os
from pathlib import Path
from typing import Dict, Optional, Tuple

import yaml

from src.core.models import SignalType, TradeSignal


class RiskEngine:
    """风控引擎"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            from src.config.paths import get_trading_config_path
            config_path = str(get_trading_config_path())
        self.config_path = config_path
        self._config = self._load_config()

    def _load_config(self) -> dict:
        """加载 trading.yaml"""
        cfg = {
            "max_position_pct": 0.30,
            "max_positions": 5,
            "min_position_pct": 0.05,
            "stop_loss_pct": 0.05,
            "take_profit_pct": 0.10,
            "max_daily_loss_pct": 0.02,
            "min_confidence": 0.70,
            "investment_mode": "medium",
        }
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if data:
                if "investment_mode" in data and data["investment_mode"]:
                    cfg["investment_mode"] = str(data["investment_mode"]).lower()
                if "risk" in data:
                    r = data["risk"]
                    cfg.update(
                        {
                            k: v
                            for k, v in r.items()
                            if k in cfg and v is not None
                        }
                    )
        except Exception:
            pass
        # 环境变量覆盖
        if os.getenv("INVESTMENT_MODE"):
            cfg["investment_mode"] = str(os.getenv("INVESTMENT_MODE")).lower()
        if os.getenv("MAX_POSITION_RATIO"):
            cfg["max_position_pct"] = float(os.getenv("MAX_POSITION_RATIO"))
        if os.getenv("STOP_LOSS_PCT"):
            cfg["stop_loss_pct"] = float(os.getenv("STOP_LOSS_PCT"))
        if os.getenv("TAKE_PROFIT_PCT"):
            cfg["take_profit_pct"] = float(os.getenv("TAKE_PROFIT_PCT"))
        if os.getenv("MAX_DAILY_LOSS_PCT"):
            cfg["max_daily_loss_pct"] = float(os.getenv("MAX_DAILY_LOSS_PCT"))
        return cfg

    @property
    def min_confidence(self) -> float:
        return self._config.get("min_confidence", 0.70)

    @property
    def investment_mode(self) -> str:
        return self._config.get("investment_mode", "medium")

    @property
    def max_position_pct(self) -> float:
        return self._config.get("max_position_pct", 0.30)

    def check_signal(
        self,
        signal: TradeSignal,
        current_price: float,
        positions: Optional[Dict] = None,
        daily_pnl_pct: float = 0,
    ) -> Tuple[bool, str]:
        """
        检查信号是否通过风控
        positions: {symbol: position_weight} 当前各标的仓位占比
        """
        positions = positions or {}

        # 1. 置信度（min_confidence=0 时不限制）
        if self.min_confidence > 0 and signal.confidence < self.min_confidence * 100:
            return False, f"置信度 {signal.confidence} 低于阈值 {self.min_confidence*100:.0f}"

        # 2. 单日亏损
        if daily_pnl_pct < -self._config.get("max_daily_loss_pct", 0.02):
            return False, "单日亏损超限，停止交易"

        # 3. 仓位
        if signal.signal == SignalType.BUY:
            # 最大持仓数量
            max_positions = int(self._config.get("max_positions", 5))
            current_count = len([w for w in positions.values() if w > 0])
            if signal.symbol not in positions and current_count >= max_positions:
                return False, f"持仓数量已达上限 {current_count}/{max_positions}"

            # 单票最大仓位
            current_weight = positions.get(signal.symbol, 0)
            new_weight = current_weight + signal.position_size
            if new_weight > self.max_position_pct:
                return False, (
                    f"仓位超限: 当前 {current_weight:.1%} + 建议 {signal.position_size:.1%} "
                    f"> {self.max_position_pct:.1%}"
                )

            # 单票最小仓位
            min_pos = float(self._config.get("min_position_pct", 0.05))
            if signal.position_size < min_pos:
                return False, f"建议仓位 {signal.position_size:.1%} 低于最小仓位 {min_pos:.1%}"

        # 4. 止损止盈合理性
        if signal.stop_loss is not None and signal.take_profit is not None:
            if signal.signal == SignalType.BUY:
                if signal.stop_loss >= current_price:
                    return False, f"买入止损价 {signal.stop_loss} 应低于当前价 {current_price}"
                if signal.take_profit <= current_price:
                    return False, f"买入止盈价 {signal.take_profit} 应高于当前价 {current_price}"
            elif signal.signal == SignalType.SELL:
                if signal.stop_loss <= current_price:
                    return False, f"卖出止损价 {signal.stop_loss} 应高于当前价 {current_price}"
                if signal.take_profit >= current_price:
                    return False, f"卖出止盈价 {signal.take_profit} 应低于当前价 {current_price}"

        return True, "通过"

    def check_stop_loss(self, position: dict, current_price: float) -> Tuple[bool, str]:
        """
        检查是否触发止损
        优先使用 AI 设定的具体价位，其次使用百分比阈值
        返回: (triggered, reason)
        """
        cost = position.get("cost") or position.get("price")
        if cost is None:
            return False, ""
        # 1. AI 设定的具体止损价
        sl_price = position.get("stop_loss")
        if sl_price is not None and sl_price > 0 and current_price <= sl_price:
            return True, f"触发止损价 {sl_price:.2f} (当前 {current_price:.2f})"
        # 2. 百分比阈值
        stop_pct = self._config.get("stop_loss_pct", 0.05)
        threshold = cost * (1 - stop_pct)
        if current_price <= threshold:
            return True, f"跌幅 {(1 - current_price / cost):.1%} 超过止损线 {stop_pct:.0%} (成本 {cost:.2f})"
        return False, ""

    def check_take_profit(self, position: dict, current_price: float) -> Tuple[bool, str]:
        """
        检查是否触发止盈
        优先使用 AI 设定的具体价位，其次使用百分比阈值
        返回: (triggered, reason)
        """
        cost = position.get("cost") or position.get("price")
        if cost is None:
            return False, ""
        # 1. AI 设定的具体止盈价
        tp_price = position.get("take_profit")
        if tp_price is not None and tp_price > 0 and current_price >= tp_price:
            return True, f"触发止盈价 {tp_price:.2f} (当前 {current_price:.2f})"
        # 2. 百分比阈值
        tp_pct = self._config.get("take_profit_pct", 0.10)
        threshold = cost * (1 + tp_pct)
        if current_price >= threshold:
            return True, f"涨幅 {(current_price / cost - 1):.1%} 超过止盈线 {tp_pct:.0%} (成本 {cost:.2f})"
        return False, ""

    def check_position_alerts(self, position: dict, current_price: float) -> list:
        """
        检查持仓的止损止盈告警
        返回告警列表: [{"type": "stop_loss"/"take_profit", "reason": str}]
        """
        alerts = []
        triggered, reason = self.check_stop_loss(position, current_price)
        if triggered:
            alerts.append({"type": "stop_loss", "reason": reason})
        triggered, reason = self.check_take_profit(position, current_price)
        if triggered:
            alerts.append({"type": "take_profit", "reason": reason})
        return alerts

    def check_daily_limit(self, daily_pnl_pct: float) -> bool:
        """是否触发单日风控（停止交易）"""
        return daily_pnl_pct <= -self._config.get("max_daily_loss_pct", 0.02)
