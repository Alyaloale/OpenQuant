"""
订单管理
追踪、记录、复盘
"""

# TODO: 实现订单管理
# - 订单状态: pending/filled/cancelled
# - 写入 SQLite trades 表
# - 支持复盘查询


class OrderManager:
    """订单管理器"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path

    def record_order(self, order: dict) -> str:
        """记录订单"""
        raise NotImplementedError("订单记录待实现")

    def get_trade_history(self, symbol: str = None, start: str = None, end: str = None) -> list:
        """查询交易历史"""
        raise NotImplementedError("交易历史查询待实现")
