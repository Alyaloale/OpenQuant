"""
模拟交易
记录成本、PnL、持仓，支持 SQLite 持久化
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from src.core.models import SignalType, TradeSignal

logger = logging.getLogger(__name__)

COMMISSION_RATE = 0.0003  # 万三


class PaperTrader:
    """模拟交易执行器"""

    def __init__(
        self,
        initial_capital: float = 10000,
        db_path: str = None,
        commission_rate: float = COMMISSION_RATE,
    ):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, dict] = {}
        self.trades: List[dict] = []
        self.commission_rate = commission_rate

        if db_path is None:
            from src.config.paths import get_db_path
            db_path = str(get_db_path())
        self.db_path = db_path
        self._init_db()
        self._load_state()

    def _init_db(self):
        """初始化数据库"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    time TEXT,
                    symbol TEXT,
                    action TEXT,
                    quantity INTEGER,
                    price REAL,
                    cost REAL,
                    revenue REAL,
                    pnl REAL,
                    extra TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    symbol TEXT PRIMARY KEY,
                    quantity INTEGER,
                    cost REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    updated TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS account (
                    key TEXT PRIMARY KEY,
                    value REAL
                )
            """)

    def _load_state(self):
        """从数据库加载持仓与现金（跨会话持久化）"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cash_row = conn.execute(
                    "SELECT value FROM account WHERE key='cash'"
                ).fetchone()
                if cash_row is not None:
                    self.cash = cash_row[0]
                rows = conn.execute(
                    "SELECT symbol, quantity, cost, stop_loss, take_profit FROM positions"
                ).fetchall()
                for row in rows:
                    sym, qty, cost, sl, tp = row
                    self.positions[sym] = {
                        "quantity": qty,
                        "cost": cost,
                        "stop_loss": sl,
                        "take_profit": tp,
                    }
        except Exception:
            pass

    def _save_account(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM account")
                conn.execute("INSERT INTO account (key, value) VALUES ('cash', ?)", (self.cash,))
        except Exception as e:
            logger.warning("保存账户状态失败: %s", e)

    def buy(
        self,
        symbol: str,
        price: float,
        size: int,
        stop_loss: float = None,
        take_profit: float = None,
    ) -> dict:
        """模拟买入"""
        if size < 100:
            logger.warning("买入数量不足 100 股")
            return {}
        cost = size * price * (1 + self.commission_rate)
        if cost > self.cash:
            logger.warning("现金不足: 需要 %.2f, 拥有 %.2f", cost, self.cash)
            return {}

        self.cash -= cost
        self.positions[symbol] = {
            "quantity": size,
            "cost": price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        }
        trade = {
            "time": datetime.now(),
            "symbol": symbol,
            "action": "BUY",
            "quantity": size,
            "price": price,
            "cost": cost,
            "revenue": None,
            "pnl": None,
        }
        self.trades.append(trade)
        self._save_trade(trade)
        self._save_positions()
        self._save_account()
        logger.info("模拟买入 %s: %d 股 @ %.2f", symbol, size, price)
        return trade

    def sell(self, symbol: str, price: float, size: int = None) -> dict:
        """模拟卖出"""
        if symbol not in self.positions:
            logger.warning("没有持仓 %s", symbol)
            return {}
        pos = self.positions[symbol]
        qty = size if size is not None else pos["quantity"]
        qty = min(qty, pos["quantity"])
        if qty <= 0:
            return {}

        revenue = qty * price * (1 - self.commission_rate)
        pnl = revenue - qty * pos["cost"]
        self.cash += revenue

        if qty >= pos["quantity"]:
            del self.positions[symbol]
        else:
            self.positions[symbol]["quantity"] -= qty

        trade = {
            "time": datetime.now(),
            "symbol": symbol,
            "action": "SELL",
            "quantity": qty,
            "price": price,
            "cost": None,
            "revenue": revenue,
            "pnl": pnl,
        }
        self.trades.append(trade)
        self._save_trade(trade)
        self._save_positions()
        self._save_account()
        logger.info("模拟卖出 %s: %d 股 @ %.2f, 盈亏: %.2f", symbol, qty, price, pnl)
        return trade

    def execute(self, signal: TradeSignal, price: float) -> bool:
        """根据信号执行交易"""
        if signal.signal == SignalType.BUY:
            amount = self.get_portfolio_value() * signal.position_size
            quantity = int(amount / price / 100) * 100
            if quantity >= 100:
                self.buy(
                    signal.symbol,
                    price,
                    quantity,
                    signal.stop_loss,
                    signal.take_profit,
                )
                return True
        elif signal.signal == SignalType.SELL:
            if signal.symbol in self.positions:
                self.sell(signal.symbol, price)
                return True
        return False

    def _save_trade(self, trade: dict):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO trades (time, symbol, action, quantity, price, cost, revenue, pnl, extra)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade["time"].isoformat() if hasattr(trade["time"], "isoformat") else str(trade["time"]),
                    trade["symbol"],
                    trade["action"],
                    trade["quantity"],
                    trade["price"],
                    trade.get("cost"),
                    trade.get("revenue"),
                    trade.get("pnl"),
                    json.dumps({}) if trade.get("extra") is None else json.dumps(trade.get("extra", {})),
                ),
            )

    def _save_positions(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM positions")
            for sym, pos in self.positions.items():
                conn.execute(
                    "INSERT INTO positions (symbol, quantity, cost, stop_loss, take_profit, updated) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        sym,
                        pos["quantity"],
                        pos["cost"],
                        pos.get("stop_loss"),
                        pos.get("take_profit"),
                        datetime.now().isoformat(),
                    ),
                )

    def get_positions(self) -> List[dict]:
        """获取当前持仓"""
        return [
            {"symbol": k, **v}
            for k, v in self.positions.items()
        ]

    def get_portfolio_value(self, prices: Optional[Dict[str, float]] = None) -> float:
        """获取组合总市值"""
        total = self.cash
        prices = prices or {}
        for sym, pos in self.positions.items():
            p = prices.get(sym, pos["cost"])
            total += pos["quantity"] * p
        return total

    def get_status(self, prices: Optional[Dict[str, float]] = None) -> dict:
        """获取账户状态"""
        pv = self.get_portfolio_value(prices)
        today = datetime.now().date()
        trades_today = sum(
            1
            for t in self.trades
            if hasattr(t["time"], "date") and t["time"].date() == today
        )
        return {
            "cash": self.cash,
            "positions": self.positions,
            "total_value": pv,
            "pnl": pv - self.initial_capital,
            "trades_today": trades_today,
        }
