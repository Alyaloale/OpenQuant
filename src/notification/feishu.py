"""飞书机器人 Webhook"""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


def send_feishu(webhook_url: str, content: str) -> bool:
    """发送飞书消息"""
    if not webhook_url or "your_token" in webhook_url:
        return False
    try:
        payload = {"msg_type": "text", "content": {"text": content}}
        with httpx.Client(timeout=5) as client:
            resp = client.post(webhook_url, json=payload)
            resp.raise_for_status()
        return True
    except Exception as e:
        logger.error("飞书通知失败: %s", e)
        return False
