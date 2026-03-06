"""提示词构建 - 将行情与指标组装为分析 Prompt"""

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
) -> str:
    """
    构建 MiniMax 分析用 Prompt
    """
    df = df.copy()
    df = calc_ma(df)
    df["RSI"] = calc_rsi(df)

    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    pct_change = (latest["收盘"] / prev["收盘"] - 1) * 100 if len(df) > 1 else 0

    # 按周期选取展示条数：日线10根，周线10根，月线全部
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

    # ETF 与股票使用不同的分析框架
    if etf:
        etf_note = "\n【标的类型】这是一只 **ETF 基金**，不是个股。分析时请注意：\n- ETF 跟踪特定指数/行业，重点分析其跟踪的行业/板块趋势\n- 关注溢价率、成交量、资金流入流出\n- 重仓股表现代替个股基本面分析\n- 不适用个股财务指标（PE/ROE等），改用行业景气度判断\n"
        holder_label = "ETF 重仓股（前10大持仓）"
        valuation_label = "ETF 实时信息（溢价率、市价等）"
        fund_flow_section = ""  # ETF 无个股资金流向
        analysis_dim_1 = "1. **行业/板块景气度**：跟踪行业的基本面、政策导向、景气周期"
        analysis_dim_3 = "3. **重仓股表现**：前10大持仓的整体走势和估值水平"
        analysis_dim_4 = "4. **ETF 资金动向**：成交量变化、溢价/折价率趋势"
    else:
        etf_note = ""
        holder_label = "筹码分布/股东持股（十大流通股东等）"
        valuation_label = "估值与财务指标（市盈率、市净率、ROE、净利润增长率等）"
        fund_flow_section = f"\n## 资金流向\n{fund_flow_str}\n"
        analysis_dim_1 = "1. **基本状况**：估值、行业地位、财务健康、经营状况"
        analysis_dim_3 = "3. **筹码分布**：股东结构、集中度、近期变动、筹码成本区"
        analysis_dim_4 = "4. **资金流动**：主力/散户资金进出、净流入流出、量价配合"

    prompt = f"""你是一位严谨的量化交易员，请对{'ETF基金' if etf else '股票'} {symbol} 进行全面分析后给出交易建议。
{etf_note}
## 投资模式（必须严格遵守）
当前为 **{mode}** 模式：{mode_hint}
请严格按此模式的分析侧重点和持仓周期给出建议。{data_note}

## 市场数据（最近{n_tail}个{period_label}K线）
{tail_df.to_string()}
{chr(10) + chr(10) + "## 月线数据（长线模式）" + chr(10) + monthly_str + chr(10) if monthly_str else ""}

## 最新价格信息
- 最新收盘价: {latest['收盘']:.2f}
- 较前周期涨跌: {pct_change:.2f}%
- 5日均线: {_safe_float(latest.get('MA5'), latest['收盘']):.2f}
- 20日均线: {_safe_float(latest.get('MA20'), latest['收盘']):.2f}
- RSI(14): {_safe_float(latest.get('RSI'), 50):.2f}

## 基本面信息
{info_str}

## 近期相关新闻
{news_str}
{fund_flow_section}
## {holder_label}
{holder_str}

## {valuation_label}
{valuation_str}

## 所属行业板块表现
{sector_str}

## 当前热门概念板块（市场热点参考）
{concept_str}

## 分析要求（必须完成以下步骤后再给出结论）
{"**【长线模式特别要求】** 你必须用年度视角思考。禁止出现'短期回调'、'近期震荡'、'周线压力'等短期词汇。你只关心：行业未来1-3年是上升还是下降？当前价格在历史估值中处于什么位置？" if mode == "long" else ""}

**分析维度需涵盖**：{'行业景气度、ETF资金动向、重仓股、技术面、市场热点、情绪面' if etf else '基本状况、市场趋势热点、筹码分布、资金流动、技术面、情绪面'}。

**第一步 - 多空因素列举**
- 做多支撑因素（至少列出2-3条）
- 做空/观望因素（至少列出2-3条）

**第二步 - 多维度交叉验证**
{analysis_dim_1}
2. **市场趋势热点**：当前板块/行业热度、政策导向、市场情绪
{analysis_dim_3}
{analysis_dim_4}
5. 技术面：{'月线/周线大趋势方向、长期均线排列' if mode == 'long' else '趋势、支撑阻力、量价关系、均线排列、RSI区域'}
6. 情绪面：新闻倾向、题材炒作
7. 若多维度结论矛盾，需说明孰轻孰重及理由

**第三步 - 综合判断并给出策略**
- 多空因素哪方更占优？
- 你必须给出明确的操作策略，不要只说"观望"
- {"长线策略要求：给出分批建仓计划（如'当前价位建仓30%，跌至X元加仓30%，跌至Y元加仓40%'），或明确说明不值得持有的理由" if mode == "long" else "给出具体的入场/出场条件和仓位管理计划"}

**第四步 - 输出结论**
仅输出下方 JSON，不要输出分析过程。分析过程在内心完成，确保结论经过全面权衡。

## 输出格式（必须严格按JSON格式，仅输出此块）
{{
    "signal": "buy/sell/hold",
    "confidence": 85,
    "reason": "详细分析理由 + 具体操作策略（{'分批建仓计划、目标持有期限' if mode == 'long' else '入场条件、止损止盈逻辑'}）",
    "stop_loss": 10.5,
    "take_profit": 12.8,
    "position_size": 0.2,
    "risk_level": "low/medium/high"
}}

注意：
- confidence 必须是 0-100 的整数
- signal 只能是 buy/sell/hold 之一
- 你应该尽量给出 buy 或 sell 的方向性判断，hold 仅在确实完全无法判断时使用
- reason 中必须包含具体的操作策略，不能只是分析
- stop_loss 和 take_profit 必须是具体价格数字
- position_size 是建议仓位比例(0-1){"，长线模式可以给较大仓位(0.2-0.5)" if mode == "long" else ""}
"""
    return prompt
