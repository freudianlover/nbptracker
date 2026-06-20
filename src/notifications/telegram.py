"""Lightweight Telegram notifier — sends messages to a chat via Bot API."""
import os
from typing import Optional

import requests
import structlog


log = structlog.get_logger()


class TelegramNotifier:
    """
    Sends messages to a Telegram chat via the Bot API.

    Reads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from environment by default.
    If either is missing, notifier is `disabled` and send() returns False silently.

    Usage:
        notifier = TelegramNotifier()
        notifier.send("USD dropped below 3.50 PLN — buy signal!")
    """

    API_BASE = "https://api.telegram.org"

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        timeout_seconds: int = 5,
    ):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.timeout = timeout_seconds
        self.enabled = bool(self.bot_token and self.chat_id)

        if not self.enabled:
            log.warning(
                "telegram_notifier_disabled",
                reason="TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set in env",
            )

    def send(self, message: str, parse_mode: str = "Markdown") -> bool:
        """
        Send message. Returns True on success, False on failure or if disabled.

        parse_mode: "Markdown" (default), "MarkdownV2", "HTML", or None
        """
        if not self.enabled:
            return False

        url = f"{self.API_BASE}/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": parse_mode,
        }

        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
        except requests.RequestException as e:
            log.warning("telegram_send_failed", error=str(e))
            return False

        if response.status_code == 200:
            log.info("telegram_sent", chars=len(message))
            return True

        log.warning(
            "telegram_send_non_200",
            status=response.status_code,
            response_text=response.text[:200],
        )
        return False
