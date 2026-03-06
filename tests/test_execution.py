"""执行模块测试"""

import pytest


def test_paper_trader_placeholder():
    """占位测试"""
    from src.execution.paper_trader import PaperTrader
    trader = PaperTrader(initial_capital=10000)
    assert trader.initial_capital == 10000
