"""AI 响应解析与验证"""

import json
import logging
from typing import Optional

from src.core.models import SignalType, TradeSignal

logger = logging.getLogger(__name__)


def _extract_json(raw: str) -> str:
    """从响应中提取 JSON，支持 ```json ... ``` 包裹"""
    raw = raw.strip()
    # 去除 markdown 代码块
    for marker in ("```json", "```"):
        if marker in raw:
            start = raw.find(marker)
            if start != -1:
                rest = raw[start + len(marker):].lstrip()
                end = rest.find("```")
                if end != -1:
                    raw = rest[:end].strip()
                else:
                    raw = rest
    json_start = raw.find("{")
    json_end = raw.rfind("}") + 1
    if json_start == -1 or json_end <= json_start:
        raise ValueError("No JSON found in response")
    return raw[json_start:json_end]


def parse_analysis_response(symbol: str, raw: str) -> TradeSignal:
    """解析 MiniMax 分析响应为 TradeSignal"""
    try:
        json_str = _extract_json(raw)
        data = json.loads(json_str)

        signal_str = str(data.get("signal", "hold")).lower()
        signal = (
            SignalType(signal_str)
            if signal_str in ("buy", "sell", "hold")
            else SignalType.HOLD
        )

        confidence = min(max(int(data.get("confidence", 0)), 0), 100)  # 限制在 0-100
        position_size = min(max(float(data.get("position_size", 0.1)), 0), 1)

        stop_loss = None
        if data.get("stop_loss") is not None:
            try:
                stop_loss = float(data["stop_loss"])
            except (TypeError, ValueError):
                pass

        take_profit = None
        if data.get("take_profit") is not None:
            try:
                take_profit = float(data["take_profit"])
            except (TypeError, ValueError):
                pass

        return TradeSignal(
            symbol=symbol,
            signal=signal,
            confidence=confidence,
            reason=data.get("reason", "No reason provided"),
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size=position_size,
            raw_response=raw,
        )
    except json.JSONDecodeError as e:
        logger.error("JSON 解析失败: %s\nResponse: %s", e, raw[:800])
        return TradeSignal(
            symbol=symbol,
            signal=SignalType.HOLD,
            confidence=0,
            reason=f"解析错误: {e}",
            raw_response=raw,
        )
    except Exception as e:
        logger.error("响应处理失败: %s\nResponse 前500字符: %s", e, raw[:500] if raw else "")
        return TradeSignal(
            symbol=symbol,
            signal=SignalType.HOLD,
            confidence=0,
            reason=f"处理错误: {e}",
            raw_response=raw,
        )
