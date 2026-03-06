"""统一配置加载：从 YAML 读取，环境变量仅保留密钥"""

import os
from pathlib import Path
from typing import Any, Dict

import yaml

from src.config.paths import get_config_dir


def _load_yaml(name: str, default: dict) -> dict:
    path = get_config_dir() / name
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else default
    except Exception:
        return default


def get_model_config(provider: str = "minimax") -> Dict[str, Any]:
    """大模型配置，从 config/model.yaml 读取（含 api_key）"""
    data = _load_yaml("model.yaml", {})
    cfg = data.get(provider, data) if isinstance(data.get(provider), dict) else data
    if not isinstance(cfg, dict):
        cfg = {}
    defaults = {
        "api_key": "",
        "base_url": "https://api.minimaxi.com/anthropic",
        "model": "MiniMax-M2.5",
        "timeout_ms": 300000,
        "temperature": 0.2,
    }
    defaults.update(cfg)
    return defaults


def get_runtime_config() -> Dict[str, Any]:
    """运行参数：交易模式、初始资金、通知"""
    data = _load_yaml("trading.yaml", {})
    rt = data.get("runtime", {})
    paper = (data.get("trading") or {}).get("paper") or {}
    return {
        "trade_mode": rt.get("trade_mode") or os.getenv("TRADE_MODE", "paper"),
        "initial_capital": float(
            rt.get("initial_capital") or paper.get("initial_capital") or os.getenv("INITIAL_CAPITAL", "10000")
        ),
        "dingtalk_webhook": (data.get("notification") or {}).get("dingtalk_webhook") or os.getenv("DINGTALK_WEBHOOK", ""),
        "feishu_webhook": (data.get("notification") or {}).get("feishu_webhook") or os.getenv("FEISHU_WEBHOOK", ""),
    }
