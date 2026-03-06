"""风控模块测试"""

import pytest

from src.core.models import SignalType, TradeSignal
from src.risk.risk_engine import RiskEngine


def test_risk_engine_init():
    """测试风控引擎初始化"""
    engine = RiskEngine()
    assert engine.config_path is not None
    assert engine.max_position_pct == 0.30


def test_risk_engine_check_confidence():
    """置信度低于阈值应不通过"""
    engine = RiskEngine()
    signal = TradeSignal(
        symbol="000001",
        signal=SignalType.BUY,
        confidence=50,
        reason="test",
        position_size=0.2,
    )
    passed, reason = engine.check_signal(signal, 10.0)
    assert not passed
    assert "置信度" in reason


def test_risk_engine_check_position():
    """仓位超限应不通过"""
    engine = RiskEngine()
    signal = TradeSignal(
        symbol="000001",
        signal=SignalType.BUY,
        confidence=80,
        reason="test",
        position_size=0.5,
    )
    positions = {"000001": 0.1}  # 已有 10%
    passed, reason = engine.check_signal(signal, 10.0, positions=positions)
    assert not passed
    assert "仓位" in reason
