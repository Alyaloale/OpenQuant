"""仓位计算"""


def calc_position_size(
    available_cash: float,
    price: float,
    max_pct: float,
    portfolio_value: float,
    min_lot: int = 100,
) -> int:
    """
    计算建议仓位（股数）
    按 100 股取整
    """
    if price <= 0 or portfolio_value <= 0:
        return 0
    max_amount = portfolio_value * max_pct
    amount = min(available_cash, max_amount)
    quantity = int(amount / price / min_lot) * min_lot
    return max(0, quantity)
