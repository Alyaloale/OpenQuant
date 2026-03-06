"""
MiniMax API 封装 (Anthropic 兼容接口)
支持重试与超时
配置来自 config/model.yaml
"""

import logging
import time
from typing import Optional

import httpx

from src.analyzer.prompt_builder import build_analysis_prompt
from src.analyzer.response_parser import parse_analysis_response
from src.config.loader import get_model_config
from src.core.models import TradeSignal

logger = logging.getLogger(__name__)

# 按投资模式定制的系统指令，确保大模型严格遵循
SYSTEM_BY_MODE = {
    "short": """你是A股短线交易员。必须按短线思维分析：持仓数日~2周。
强制侧重点：5日/20日均线、RSI超买超卖、量价配合、短期支撑阻力。
禁止：讨论行业周期、长期估值、月线趋势。
你必须给出明确的 buy 或 sell 建议和具体的入场策略（何时买、买多少、止损止盈位）。
仅输出 JSON，不要分析过程。""",
    "medium": """你是A股中线交易员。必须按中线思维分析：持仓数周~3月。
强制侧重点：20日/60日均线趋势、技术面与基本面并重、估值合理性、波段高低点。
勿过度关注：单日波动、RSI短期拐点。
你必须给出明确的操作策略（建仓/加仓/减仓/清仓）和具体的执行条件。
仅输出 JSON，不要分析过程。""",
    "long": """你是A股长线价值投资者。必须按长线思维分析：持仓数月~数年。
你的视角是以年为单位的，短期1-3个月的波动对你毫无意义。
强制侧重点：月线大趋势、行业景气周期位置（上升/见顶/下行/触底）、基本面估值水平、分红回报率。
严禁出现以下词汇和分析：短期回调、周线震荡、近期涨跌、短期压力、短期支撑——这些都是噪音。
你要回答的核心问题是：这个标的在未来1-3年是否值得持有？当前价格相对长期价值是高估还是低估？
给出明确的长线策略：是否值得建仓/持有，以及分批建仓计划。
仅输出 JSON，不要分析过程。""",
}


def _build_system_prompt(mode: str, trade_mode: str = "paper") -> str:
    mode = (mode or "medium").lower()
    specific = SYSTEM_BY_MODE.get(mode, SYSTEM_BY_MODE["medium"])
    base = "分析时兼顾多空，多维度交叉验证后给出结论。"
    if trade_mode == "paper":
        base += "\n当前为模拟盘模式，目的是学习和验证策略。你应该更果断地给出 buy 或 sell 建议，不要轻易给 hold。即使把握只有60%也应该给出方向性判断和具体策略，因为模拟盘的核心价值在于积累决策经验。"
    return f"{specific}\n{base}"


class MiniMaxClient:
    """AI 分析客户端，支持 MiniMax / DeepSeek 等多模型，配置来自 config/model.yaml"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
        trade_mode: str = "paper",
        provider: Optional[str] = None,
    ):
        self.provider = (provider or "minimax").lower()
        cfg = get_model_config(self.provider)
        self.api_key = api_key or cfg.get("api_key", "")
        self.base_url = (base_url or cfg.get("base_url", "https://api.minimaxi.com/anthropic")).rstrip("/")
        self.model = model or cfg.get("model", "MiniMax-M2.5")
        self.timeout = timeout or (int(cfg.get("timeout_ms", 300000)) / 1000.0)
        self.temperature = float(cfg.get("temperature", 0.2))
        self.trade_mode = trade_mode

        if not self.api_key:
            raise ValueError(f"未设置 API Key，请在 config/model.yaml 的 {self.provider}.api_key 中配置")

    def analyze(
        self,
        symbol: str,
        df,
        info=None,
        news: Optional[list] = None,
        fund_flow=None,
        holder=None,
        valuation=None,
        sector=None,
        concept_hot=None,
        data_period: str = "daily",
        df_monthly=None,
        investment_mode: str = "medium",
    ) -> TradeSignal:
        """
        分析股票并返回交易信号
        """
        prompt = build_analysis_prompt(
            symbol, df, info, news,
            fund_flow=fund_flow,
            holder=holder,
            valuation=valuation,
            sector=sector,
            concept_hot=concept_hot,
            data_period=data_period,
            df_monthly=df_monthly,
            investment_mode=investment_mode,
        )
        n_bars = len(df)
        n_monthly = len(df_monthly) if df_monthly is not None and not df_monthly.empty else 0
        period_desc = "daily(回退)" if data_period == "daily_fallback" else data_period
        logger.info("大模型输入: %s 模式=%s 数据=%s K线%d根%s", symbol, investment_mode, period_desc, n_bars, f" 月线{n_monthly}根" if n_monthly else "")
        raw = self._call_api(prompt, investment_mode=investment_mode)
        return parse_analysis_response(symbol, raw)

    def _call_api(self, prompt: str, max_retries: int = 3, investment_mode: str = "medium") -> str:
        """调用 AI API（根据 provider 切换路径和格式）"""
        if self.provider == "deepseek":
            url = f"{self.base_url}/chat/completions"
        else:
            url = f"{self.base_url}/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        if self.provider == "minimax":
            headers["x-api-key"] = self.api_key
        system_content = _build_system_prompt(investment_mode, self.trade_mode)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 2000,
            "temperature": self.temperature,
        }

        last_error = None
        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    result = resp.json()

                # 兼容 MiniMax Anthropic 格式: content 为 block 列表，含 type=thinking/text
                text = ""
                if "content" in result and result["content"]:
                    for block in result["content"]:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text += block.get("text", "")
                    # 若无 text 块，尝试首块（兼容旧格式）
                    if not text and result["content"]:
                        first = result["content"][0]
                        if isinstance(first, dict):
                            text = first.get("text", first.get("thinking", ""))
                if not text and "choices" in result and result["choices"]:
                    msg = result["choices"][0].get("message", {})
                    text = msg.get("content", "")
                if not text:
                    logger.debug("API 原始响应: %s", str(result)[:500])
                    raise ValueError(f"无法解析 API 响应，content 为空: {list(result.keys())}")

                return text
            except (httpx.HTTPError, ValueError) as e:
                last_error = e
                logger.warning("API 调用失败 (尝试 %d/%d): %s", attempt + 1, max_retries, e)
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
        raise last_error


__all__ = ["MiniMaxClient"]
