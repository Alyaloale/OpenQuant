"""提示词构建 - 将行情与指标组装为分析 Prompt
分析框架：大盘 → 板块热点 → 板块龙头 → 个股
"""

import pandas as pd

from src.data.technical_indicators import calc_ma, calc_rsi


def _safe_float(val, default: float = 0):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


MODE_HINTS = {
    "short": "短线（持仓数日~2周）：侧重短期技术面、量价、超买超卖，快进快出。",
    "medium": "中线（持仓数周~3月）：技术面与基本面均衡，关注趋势与估值。",
    "long": "长线（持仓数月~年）：侧重基本面、估值、行业景气、分红，忽略短期波动。",
}


def _is_etf(symbol: str) -> bool:
    s = str(symbol).strip().zfill(6)
    return s.startswith(("51", "52", "58", "159"))


def build_analysis_prompt(
    symbol: str,
    df: pd.DataFrame,
    info: pd.DataFrame = None,
    news: list = None,
    fund_flow: pd.DataFrame = None,
    holder: pd.DataFrame = None,
    valuation: pd.DataFrame = None,
    sector: pd.DataFrame = None,
    concept_hot: pd.DataFrame = None,
    data_period: str = "daily",
    df_monthly: pd.DataFrame = None,
    investment_mode: str = "medium",
    market_overview: pd.DataFrame = None,
    sector_rank: pd.DataFrame = None,
) -> str:
    """
    构建分析 Prompt — 自上而下框架：大盘 → 板块 → 个股
    """
    df = df.copy()
    df = calc_ma(df)
    df["RSI"] = calc_rsi(df)

    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    pct_change = (latest["收盘"] / prev["收盘"] - 1) * 100 if len(df) > 1 else 0

    # 按周期选取展示条数
    n_tail = 10 if data_period in ("daily", "daily_fallback", "weekly") else min(24, len(df))
    cols = ["日期", "开盘", "收盘", "最高", "最低", "成交量"]
    ma_cols = [c for c in df.columns if c.startswith("MA")]
    display_cols = cols + ma_cols + ["RSI"]
    display_cols = [c for c in display_cols if c in df.columns]
    tail_df = df.tail(n_tail)[display_cols]
    period_label = {"daily": "交易日", "daily_fallback": "交易日(周线回退)", "weekly": "周", "monthly": "月"}.get(data_period, "日")

    info_str = info.to_string() if info is not None and not info.empty else "暂无数据"
    news_str = "\n".join(f"- {n}" for n in (news or [])[:5]) if news else "暂无新闻"
    fund_flow_str = fund_flow.to_string() if fund_flow is not None and not fund_flow.empty else "暂无数据"
    holder_str = holder.to_string() if holder is not None and not holder.empty else "暂无数据"
    valuation_str = valuation.to_string() if valuation is not None and not valuation.empty else "暂无数据"
    sector_str = sector.to_string() if sector is not None and not sector.empty else "暂无数据"
    concept_str = concept_hot.to_string() if concept_hot is not None and not concept_hot.empty else "暂无数据"
    market_str = market_overview.to_string() if market_overview is not None and not market_overview.empty else "暂无数据"
    sector_rank_str = sector_rank.to_string() if sector_rank is not None and not sector_rank.empty else "暂无数据"

    monthly_str = ""
    if df_monthly is not None and not df_monthly.empty:
        df_m = df_monthly.copy()
        df_m = calc_ma(df_m)
        df_m["RSI"] = calc_rsi(df_m)
        mc = ["日期", "开盘", "收盘", "最高", "最低", "成交量"]
        mc = mc + [c for c in df_m.columns if c.startswith("MA") or c == "RSI"]
        mc = [c for c in mc if c in df_m.columns]
        monthly_str = df_m[mc].tail(12).to_string()

    etf = _is_etf(symbol)
    mode = investment_mode.lower() if investment_mode else "medium"
    mode_hint = MODE_HINTS.get(mode, MODE_HINTS["medium"])
    data_note = ""
    if data_period == "daily_fallback" and mode == "long":
        data_note = "\n【重要】当前为日线数据（周线接口不可用），但你必须按 long 模式分析：侧重中长期趋势、行业周期、估值，勿被日线短期波动干扰。\n"

    # ETF vs 股票框架差异
    if etf:
        etf_note = "\n【标的类型】这是一只 **ETF 基金**，不是个股。分析时请注意：\n- ETF 跟踪特定指数/行业，重点分析其跟踪的行业/板块趋势\n- 关注溢价率、成交量、资金流入流出\n- 重仓股表现代替个股基本面分析\n- 不适用个股财务指标（PE/ROE等），改用行业景气度判断\n"
        holder_label = "ETF 重仓股（前10大持仓）"
        valuation_label = "ETF 实时信息（溢价率、市价等）"
        fund_flow_section = ""
    else:
        etf_note = ""
        holder_label = "筹码分布/股东持股（十大流通股东等）"
        valuation_label = "估值与财务指标（市盈率、市净率、ROE、净利润增长率等）"
        fund_flow_section = f"\n## 个股资金流向\n{fund_flow_str}\n"

    prompt = f"""你是一位严谨的量化交易员，请对{'ETF基金' if etf else '股票'} {symbol} 进行**自上而下**的全面分析后给出交易建议。
{etf_note}
## 投资模式（必须严格遵守）
当前为 **{mode}** 模式：{mode_hint}
请严格按此模式的分析侧重点和持仓周期给出建议。{data_note}

━━━━━━━━━━ 第一层：大盘环境 ━━━━━━━━━━

## 大盘主要指数
{market_str}

## 当前热门概念板块（涨幅排行）
{concept_str}

━━━━━━━━━━ 第二层：板块分析 ━━━━━━━━━━

## 行业板块涨跌排行（今日最强/最弱）
{sector_rank_str}

## {symbol} 所属行业板块表现
{sector_str}

━━━━━━━━━━ 第三层：个股分析 ━━━━━━━━━━

## 基本面信息
{info_str}

## 近期相关新闻
{news_str}
{fund_flow_section}
## {holder_label}
{holder_str}

## {valuation_label}
{valuation_str}

## 市场数据（最近{n_tail}个{period_label}K线）
{tail_df.to_string()}
{chr(10) + chr(10) + "## 月线数据（长线模式）" + chr(10) + monthly_str + chr(10) if monthly_str else ""}

## 最新价格信息
- 最新收盘价: {latest['收盘']:.2f}
- 较前周期涨跌: {pct_change:.2f}%
- 5日均线: {_safe_float(latest.get('MA5'), latest['收盘']):.2f}
- 20日均线: {_safe_float(latest.get('MA20'), latest['收盘']):.2f}
- RSI(14): {_safe_float(latest.get('RSI'), 50):.2f}

━━━━━━━━━━ 分析要求 ━━━━━━━━━━

{"**【长线模式特别要求】** 你必须用年度视角思考。禁止出现'短期回调'、'近期震荡'、'周线压力'等短期词汇。你只关心：行业未来1-3年是上升还是下降？当前价格在历史估值中处于什么位置？" if mode == "long" else ""}

**你必须严格按照以下自上而下的分析框架，逐层推导后再给出结论：**

**第一步 - 大盘环境判断**
- 当前大盘处于什么状态（上涨/震荡/下跌）？量能如何？
- 市场整体风险偏好如何？是否适合操作？

**第二步 - 板块热点与轮动**
- 今日哪些板块最强？资金主攻方向是什么？
- {symbol} 所在板块处于什么位置（领涨/跟涨/滞涨/调整）？
- 该板块内谁是龙头？{symbol} 在板块中的地位如何？是龙头、跟风还是补涨？

**第三步 - 个股多空因素**
- 做多支撑因素（至少2-3条，结合基本面、资金面、技术面）
- 做空/观望因素（至少2-3条）

**第四步 - 个股多维度交叉验证**
1. {'行业景气度、ETF资金动向' if etf else '基本面：估值、行业地位、财务健康'}
2. 技术面：{'月线/周线大趋势方向、长期均线排列' if mode == 'long' else '趋势、支撑阻力、量价关系、均线排列、RSI区域'}
3. {'重仓股整体走势' if etf else '筹码与资金：主力动向、资金流入流出'}
4. 情绪面与催化剂：新闻、题材、政策
5. 若多维度结论矛盾，需说明孰轻孰重及理由

**第五步 - 综合判断并给出策略**
- 从大盘→板块→个股，多空哪方更占优？
- 你必须给出明确的操作策略
- {"长线策略：给出分批建仓计划（如'当前价位建仓30%，跌至X元加仓30%'），或明确说明不值得持有" if mode == "long" else "给出具体的入场/出场条件和仓位管理计划"}

**第六步 - 输出结论**
在内心完成上述全部分析后，将分析过程和结论一起输出到 reason 字段中。

## 输出格式（必须严格按JSON格式）
{{
    "signal": "buy/sell/hold",
    "confidence": 85,
    "reason": "【大盘】...【板块】...板块龙头是...，{symbol}在板块中属于...【个股】多空因素...【策略】具体操作计划...",
    "stop_loss": 10.5,
    "take_profit": 12.8,
    "position_size": 0.2,
    "risk_level": "low/medium/high"
}}

注意：
- confidence 必须是 0-100 的整数
- signal 只能是 buy/sell/hold 之一
- 你应该尽量给出 buy 或 sell 的方向性判断，hold 仅在确实完全无法判断时使用
- reason 中**必须包含大盘、板块、个股三个层面的分析**，以及具体操作策略
- stop_loss 和 take_profit 必须是具体价格数字
- position_size 是建议仓位比例(0-1){"，长线模式可以给较大仓位(0.2-0.5)" if mode == "long" else ""}
"""
    return prompt
