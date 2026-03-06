"""核心数据模型"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SignalType(Enum):
    """交易信号类型"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class TradeSignal:
    """交易信号"""
    symbol: str
    signal: SignalType
    confidence: float
    reason: str
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_size: float = 0.1
    raw_response: str = ""
