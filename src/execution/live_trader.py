"""
实盘交易接口（预留）
后续接入 QMT / 聚宽 / IB
"""

# TODO: Phase 5 实盘接入
# - QMT (XtQuant)
# - 聚宽 JoinQuant
# - IB (Interactive Brokers)


class LiveTrader:
    """实盘交易执行器（预留）"""

    def __init__(self, broker: str = "qmt"):
        self.broker = broker

    def connect(self) -> bool:
        raise NotImplementedError("实盘接口待接入")
