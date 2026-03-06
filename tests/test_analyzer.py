"""AI 分析模块测试"""

import os
import pytest


def test_minimax_client_init():
    """测试 MiniMax 客户端初始化"""
    os.environ["ANTHROPIC_AUTH_TOKEN"] = "test-key"
    try:
        from src.analyzer.minimax_client import MiniMaxClient

        client = MiniMaxClient(api_key="test-key")
        assert client.base_url == "https://api.minimaxi.com/anthropic"
        assert client.model == "MiniMax-M2.5"
    finally:
        os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)


def test_minimax_client_requires_key():
    """未设置 API Key 时应抛出异常"""
    token = os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)
    try:
        from src.analyzer.minimax_client import MiniMaxClient

        with pytest.raises(ValueError, match="ANTHROPIC_AUTH_TOKEN"):
            MiniMaxClient()
    finally:
        if token:
            os.environ["ANTHROPIC_AUTH_TOKEN"] = token
