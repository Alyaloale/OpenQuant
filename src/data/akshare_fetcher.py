"""
AKShare 数据获取
日线行情、基本面、新闻
优先东方财富，失败时自动切换腾讯/新浪数据源
"""

import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

import akshare as ak
import pandas as pd

logger = logging.getLogger(__name__)

FETCH_DELAY = 1.5
MAX_RETRIES = 2

# 目标列名（与 prompt_builder 一致）
COL_DATE = "日期"
COL_OPEN = "开盘"
COL_CLOSE = "收盘"
COL_HIGH = "最高"
COL_LOW = "最低"
COL_VOL = "成交量"


def _to_exchange_symbol(symbol: str) -> str:
    """000001 -> sz000001, 600519 -> sh600519"""
    code = symbol.strip().upper().split(".")[0]
    if code.startswith(("6", "5", "9")):
        return f"sh{code}"
    return f"sz{code}"


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """统一列名为中文"""
    mapping = {
        "date": COL_DATE,
        "open": COL_OPEN,
        "close": COL_CLOSE,
        "high": COL_HIGH,
        "low": COL_LOW,
        "volume": COL_VOL,
        "amount": "成交额",
    }
    df = df.rename(columns={k: v for k, v in mapping.items() if k in df.columns})
    if COL_VOL not in df.columns and "成交额" in df.columns and COL_CLOSE in df.columns:
        df[COL_VOL] = (df["成交额"] / df[COL_CLOSE]).astype(int)
    if COL_DATE in df.columns and df[COL_DATE].dtype == object:
        df[COL_DATE] = pd.to_datetime(df[COL_DATE]).dt.strftime("%Y-%m-%d")
    return df


def _fetch_em(symbol: str, start: str, end: str, adjust: str, period: str = "daily") -> pd.DataFrame:
    """东方财富 stock_zh_a_hist，支持 period: daily/weekly/monthly"""
    df = ak.stock_zh_a_hist(
        symbol=symbol,
        period=period,
        start_date=start,
        end_date=end,
        adjust=adjust,
    )
    return df if df is not None and not df.empty else pd.DataFrame()


def _fetch_sina(symbol: str, start: str, end: str) -> pd.DataFrame:
    """新浪 stock_zh_a_daily"""
    ex = _to_exchange_symbol(symbol)
    df = ak.stock_zh_a_daily(symbol=ex, start_date=start, end_date=end)
    return df if df is not None and not df.empty else pd.DataFrame()


def _fetch_tx(symbol: str, start: str, end: str) -> pd.DataFrame:
    """腾讯 stock_zh_a_hist_tx"""
    ex = _to_exchange_symbol(symbol)
    df = ak.stock_zh_a_hist_tx(symbol=ex, start_date=start, end_date=end)
    return df if df is not None and not df.empty else pd.DataFrame()


def fetch_daily(
    symbol: str,
    start: str = None,
    end: str = None,
    days: int = 30,
    adjust: str = "qfq",
) -> pd.DataFrame:
    """
    获取日线行情
    数据源优先级: 东方财富 -> 新浪 -> 腾讯
    """
    end = end or datetime.now().strftime("%Y%m%d")
    start = start or (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    sources = [
        ("东方财富", lambda: _fetch_em(symbol, start, end, adjust, "daily")),
        ("新浪", lambda: _fetch_sina(symbol, start, end)),
        ("腾讯", lambda: _fetch_tx(symbol, start, end)),
    ]
    for name, fetch_fn in sources:
        for attempt in range(MAX_RETRIES):
            try:
                df = fetch_fn()
                if df is not None and not df.empty:
                    df = _normalize_columns(df.copy())
                    if COL_CLOSE not in df.columns:
                        continue
                    logger.info("日线数据 %s 来自 %s", symbol, name)
                    return df
            except Exception as e:
                logger.debug("%s 接口 %s 失败: %s", name, symbol, e)
                if attempt < MAX_RETRIES - 1:
                    time.sleep(FETCH_DELAY)
    logger.error("获取日线失败 %s，所有数据源均不可用", symbol)
    return pd.DataFrame()


def fetch_weekly(symbol: str, weeks: int = 52, adjust: str = "qfq") -> pd.DataFrame:
    """获取周线（仅东方财富支持）"""
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=weeks * 7)).strftime("%Y%m%d")
    try:
        df = _fetch_em(symbol, start, end, adjust, "weekly")
        if df is not None and not df.empty:
            df = _normalize_columns(df.copy())
            if COL_CLOSE in df.columns:
                logger.info("周线数据 %s 来自 东方财富 (%d周)", symbol, len(df))
                return df
    except Exception as e:
        logger.debug("获取周线失败 %s: %s", symbol, e)
    return pd.DataFrame()


def fetch_monthly(symbol: str, months: int = 24, adjust: str = "qfq") -> pd.DataFrame:
    """获取月线（仅东方财富支持）"""
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=months * 31)).strftime("%Y%m%d")
    try:
        df = _fetch_em(symbol, start, end, adjust, "monthly")
        if df is not None and not df.empty:
            df = _normalize_columns(df.copy())
            if COL_CLOSE in df.columns:
                logger.info("月线数据 %s 来自 东方财富 (%d月)", symbol, len(df))
                return df
    except Exception as e:
        logger.debug("获取月线失败 %s: %s", symbol, e)
    return pd.DataFrame()


def fetch_stock_info(symbol: str) -> pd.DataFrame:
    """获取个股基本面信息（东方财富，失败不阻塞）"""
    try:
        return ak.stock_individual_info_em(symbol=symbol)
    except Exception as e:
        logger.debug("获取基本面失败 %s: %s", symbol, e)
        return pd.DataFrame()


def fetch_fund_flow(symbol: str) -> pd.DataFrame:
    """个股资金流向（东方财富，失败不阻塞）"""
    try:
        df = ak.stock_fund_flow_individual(symbol=symbol)
        return df if df is not None and not df.empty else pd.DataFrame()
    except Exception as e:
        logger.debug("获取资金流向失败 %s: %s", symbol, e)
        return pd.DataFrame()


def fetch_holder_stats(symbol: str) -> pd.DataFrame:
    """股东持股/筹码相关统计（东方财富，失败不阻塞）"""
    try:
        df = ak.stock_gdfx_free_top_10_em(symbol=symbol)
        return df if df is not None and not df.empty else pd.DataFrame()
    except Exception as e:
        logger.debug("获取股东持股失败 %s: %s", symbol, e)
        return pd.DataFrame()


def fetch_stock_news(symbol: str, limit: int = 5) -> List[str]:
    """获取个股相关新闻（东方财富，失败不阻塞）"""
    try:
        df = ak.stock_news_em(symbol=symbol)
        if df is None or df.empty:
            return []
        col = "新闻标题" if "新闻标题" in df.columns else df.columns[0]
        return df[col].head(limit).tolist()
    except Exception as e:
        logger.debug("获取新闻失败 %s: %s", symbol, e)
        return []


def fetch_stock_valuation(symbol: str) -> pd.DataFrame:
    """
    获取估值与财务指标（市盈率、市净率、ROE、净利润增长率等）
    数据源: 新浪财务指标 + 东方财富全市场 spot(PE/PB)
    """
    rows = []
    # 1. 财务指标：ROE、销售净利率、净利润增长率（新浪）
    try:
        start_year = str(datetime.now().year - 2)
        df_fin = ak.stock_financial_analysis_indicator(symbol=symbol, start_year=start_year)
        if df_fin is not None and not df_fin.empty:
            last = df_fin.iloc[-1]
            for col in ["净资产收益率(%)", "销售净利率(%)", "净利润增长率(%)", "资产负债率(%)"]:
                if col in df_fin.columns and pd.notna(last.get(col)):
                    rows.append({"指标": col, "数值": last[col]})
    except Exception as e:
        logger.debug("获取财务指标失败 %s: %s", symbol, e)
    # 2. PE/PB：东方财富全市场 spot 筛选
    try:
        df_spot = ak.stock_zh_a_spot_em()
        if df_spot is not None and not df_spot.empty:
            code_col = "代码" if "代码" in df_spot.columns else df_spot.columns[0]
            row = df_spot[df_spot[code_col].astype(str).str.zfill(6) == str(symbol).zfill(6)]
            if not row.empty:
                r = row.iloc[0]
                for label, col in [("市盈率-动态", "市盈率-动态"), ("市净率", "市净率")]:
                    if col in df_spot.columns and pd.notna(r.get(col)):
                        rows.append({"指标": label, "数值": r[col]})
    except Exception as e:
        logger.debug("获取PE/PB失败 %s: %s", symbol, e)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def fetch_sector_info(industry_name: str) -> pd.DataFrame:
    """
    获取行业板块表现（涨跌幅、领涨股等）
    industry_name: 行业名称，通常来自 stock_individual_info_em 的 行业 字段
    """
    if not industry_name or not str(industry_name).strip():
        return pd.DataFrame()
    try:
        df = ak.stock_board_industry_name_em()
        if df is None or df.empty:
            return pd.DataFrame()
        name_col = "板块名称" if "板块名称" in df.columns else "名称"
        if name_col not in df.columns:
            name_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]
        mask = df[name_col].astype(str).str.contains(str(industry_name).strip(), na=False, regex=False)
        matched = df[mask]
        if not matched.empty:
            return matched.head(1)
        return pd.DataFrame()
    except Exception as e:
        logger.debug("获取板块信息失败 %s: %s", industry_name, e)
        return pd.DataFrame()


def fetch_concept_hot(limit: int = 10) -> pd.DataFrame:
    """
    获取热门概念板块（涨跌幅排行）
    供分析市场热点参考
    """
    try:
        df = ak.stock_board_concept_name_em()
        if df is None or df.empty:
            return pd.DataFrame()
        pct_col = "涨跌幅" if "涨跌幅" in df.columns else df.columns[2] if len(df.columns) > 2 else df.columns[-1]
        df_sorted = df.sort_values(by=pct_col, ascending=False, na_position="last")
        return df_sorted.head(limit)
    except Exception as e:
        logger.debug("获取概念板块失败: %s", e)
        return pd.DataFrame()


def get_stock_data(
    symbol: str,
    days: int = 30,
    investment_mode: str = "medium",
) -> Tuple[pd.DataFrame, pd.DataFrame, List[str], pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, str, Optional[pd.DataFrame]]:
    """
    获取完整股票数据，按投资模式选择 K 线周期：
    - short: 日线 20 根
    - medium: 日线 60 根
    - long: 周线 52 根 + 月线 24 根
    返回: (df, info, news, fund_flow, holder, valuation, sector, concept_hot, data_period, df_monthly)
    """
    mode = (investment_mode or "medium").lower()
    df_monthly: Optional[pd.DataFrame] = None

    # 执行/取价等场景：始终用日线
    if days <= 3:
        df = fetch_daily(symbol, days=max(days, 3))
        data_period = "daily"
    elif mode == "short":
        df = fetch_daily(symbol, days=20)
        data_period = "daily"
    elif mode == "long":
        df = fetch_weekly(symbol, weeks=52)
        if df.empty:
            logger.warning("%s long模式周线获取失败，回退日线60根", symbol)
            df = fetch_daily(symbol, days=60)
            data_period = "daily_fallback"  # 标记为回退，prompt 中特别说明
        else:
            data_period = "weekly"
            time.sleep(FETCH_DELAY)
            df_monthly = fetch_monthly(symbol, months=24)
    else:
        df = fetch_daily(symbol, days=min(60, max(days, 30)))
        data_period = "daily"

    if df.empty:
        empty = pd.DataFrame()
        return df, empty, [], empty, empty, empty, empty, empty, data_period, None
    time.sleep(FETCH_DELAY)
    info = fetch_stock_info(symbol)
    time.sleep(FETCH_DELAY)
    news = fetch_stock_news(symbol)
    time.sleep(FETCH_DELAY)
    fund_flow = fetch_fund_flow(symbol)
    time.sleep(FETCH_DELAY)
    holder = fetch_holder_stats(symbol)
    time.sleep(FETCH_DELAY)
    valuation = fetch_stock_valuation(symbol)
    time.sleep(FETCH_DELAY)
    industry_name = ""
    if info is not None and not info.empty and "item" in info.columns and "value" in info.columns:
        ir = info[info["item"].astype(str).str.contains("行业", na=False)]
        if not ir.empty:
            industry_name = str(ir.iloc[0]["value"]).strip()
    sector = fetch_sector_info(industry_name) if industry_name else pd.DataFrame()
    concept_hot = fetch_concept_hot(limit=8)
    return df, info, news, fund_flow, holder, valuation, sector, concept_hot, data_period, df_monthly


def fetch_realtime(symbol: str) -> dict:
    """
    获取实时/最新价格
    优先级: 东方财富 spot -> 新浪 spot -> 日线最后一笔收盘价
    注意: 免费接口有 1-15 秒延迟，非交易所直连
    """
    # 1. 东方财富全市场 spot（需筛选）
    for fetch_fn, name in [
        (_fetch_spot_em, "东方财富"),
        (_fetch_spot_sina, "新浪"),
    ]:
        try:
            d = fetch_fn(symbol)
            if d:
                d["source"] = name
                return d
        except Exception as e:
            logger.debug("实时价 %s 失败 %s: %s", name, symbol, e)
    # 2. 回退到日线最后一笔
    df = fetch_daily(symbol, days=3)
    if not df.empty:
        row = df.iloc[-1]
        return {
            "symbol": symbol,
            "price": float(row[COL_CLOSE]),
            "source": "日线(非实时)",
            "date": str(row[COL_DATE]),
        }
    return {}


def _fetch_spot_em(symbol: str) -> dict:
    """东方财富实时（全市场后筛选）"""
    df = ak.stock_zh_a_spot_em()
    if df is None or df.empty:
        return {}
    code_col = "代码" if "代码" in df.columns else df.columns[0]
    row = df[df[code_col].astype(str).str.zfill(6) == str(symbol).zfill(6)]
    if row.empty:
        return {}
    r = row.iloc[0]
    price_col = "最新价" if "最新价" in df.columns else "price"
    return {
        "symbol": symbol,
        "price": float(r.get(price_col, r.iloc[2])),
        "change_pct": float(r.get("涨跌幅", 0)) if "涨跌幅" in df.columns else None,
        "volume": float(r.get("成交量", 0)) if "成交量" in df.columns else None,
    }


def _fetch_spot_sina(symbol: str) -> dict:
    """新浪实时（全市场后筛选）"""
    df = ak.stock_zh_a_spot()
    if df is None or df.empty:
        return {}
    code_col = df.columns[0]
    row = df[df[code_col].astype(str).str.zfill(6) == str(symbol).zfill(6)]
    if row.empty:
        return {}
    r = row.iloc[0]
    # 新浪列: 代码, 名称, 最新价, 涨跌幅, 涨跌额, 成交量...
    price_idx = 2 if len(r) > 2 else 0
    return {
        "symbol": symbol,
        "price": float(r.iloc[price_idx]) if len(r) > price_idx else 0,
    }


def add_to_watchlist(symbol: str, path: str = None) -> bool:
    """添加股票到自选股"""
    symbols = load_watchlist(path)
    code = str(symbol).strip().zfill(6)
    if code in [s.zfill(6) for s in symbols]:
        return False
    if path is None:
        from src.config.paths import get_watchlist_path
        path = str(get_watchlist_path())
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"\n{code}")
    return True


def remove_from_watchlist(symbol: str, path: str = None) -> bool:
    """从自选股移除"""
    symbols = load_watchlist(path)
    code = str(symbol).strip().zfill(6)
    new_list = [s for s in symbols if s.zfill(6) != code]
    if len(new_list) == len(symbols):
        return False
    if path is None:
        from src.config.paths import get_watchlist_path
        path = str(get_watchlist_path())
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(new_list) + "\n")
    return True


def load_watchlist(path: str = None) -> List[str]:
    """从文件加载自选股列表"""
    if path is None:
        from src.config.paths import get_watchlist_path
        path = get_watchlist_path()
    path = Path(path)
    if not path.exists():
        return ["000001", "000858", "600519", "000333", "002594"]
    symbols = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                code = line.split()[0] if line.split() else line
                symbols.append(code)
    return symbols if symbols else ["000001", "600519"]


def get_stock_pool(source: str = "hot", limit: int = 50) -> List[str]:
    """
    获取待选股池，供 AI 选股使用
    source: hot(人气榜) / watchlist(自选股)
    """
    try:
        if source == "hot":
            df = ak.stock_hot_rank_em()
            if df is not None and not df.empty:
                # 列名可能为 代码 或 股票代码
                for col in ["代码", "股票代码", df.columns[1]]:
                    if col in df.columns:
                        return df[col].astype(str).str.zfill(6).head(limit).tolist()
        elif source == "index":
            df = ak.stock_zh_index_spot_em()
            if df is not None and not df.empty:
                col = "代码" if "代码" in df.columns else df.columns[0]
                return df[col].astype(str).str.zfill(6).head(limit).tolist()
    except Exception as e:
        logger.warning("获取股池失败 %s: %s", source, e)
    return load_watchlist()[:limit]


__all__ = [
    "fetch_daily",
    "fetch_weekly",
    "fetch_monthly",
    "fetch_realtime",
    "fetch_stock_info",
    "fetch_stock_news",
    "fetch_stock_valuation",
    "fetch_sector_info",
    "fetch_concept_hot",
    "get_stock_data",
    "get_stock_pool",
    "load_watchlist",
    "add_to_watchlist",
    "remove_from_watchlist",
]
