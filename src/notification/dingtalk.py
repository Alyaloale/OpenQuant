"""钉钉机器人 Webhook"""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


def send_dingtalk(
    webhook_url: str,
    content: str,
    msg_type: str = "text",
) -> bool:
    """发送钉钉消息"""
    if not webhook_url or "your_token" in webhook_url:
        return False
    try:
        if msg_type == "markdown":
            payload = {"msgtype": "markdown", "markdown": {"title": "OpenQuant", "text": content}}
        else:
            payload = {"msgtype": "text", "text": {"content": content}}
        with httpx.Client(timeout=5) as client:
            resp = client.post(webhook_url, json=payload)
            resp.raise_for_status()
        return True
    except Exception as e:
        logger.error("钉钉通知失败: %s", e)
        return False
