"""技术指标计算 - MA / RSI / 成交量"""

from typing import List, Optional

import pandas as pd


def calc_ma(
    df: pd.DataFrame,
    price_col: str = "收盘",
    windows: Optional[List[int]] = None,
) -> pd.DataFrame:
    """计算移动平均线"""
    windows = windows or [5, 10, 20, 60]
    out = df.copy()
    for w in windows:
        if len(df) >= w:
            out[f"MA{w}"] = df[price_col].rolling(w).mean()
    return out


def calc_rsi(
    df: pd.DataFrame,
    price_col: str = "收盘",
    period: int = 14,
) -> pd.Series:
    """计算 RSI"""
    delta = df[price_col].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)  # 避免除零
    return 100 - (100 / (1 + rs))
