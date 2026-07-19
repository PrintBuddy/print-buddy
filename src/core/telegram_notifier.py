import httpx

from .config import settings
from .logger import logger


class TelegramNotifier:
    """Sends/edits Telegram messages directly via the Bot API, bypassing the
    bot process entirely. Used for recharge requests created from the web
    app, where there's no bot conversation already in flight to do the
    send. Telegram routes the resulting callback_query (button press) to
    whichever service is polling with this bot token — i.e. the bot
    process — regardless of which process sent the original message, so
    the bot's existing approve/reject handling needs no changes to receive
    button presses on messages this class sent."""

    def __init__(self):
        self._base_url = (
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"
            if settings.TELEGRAM_BOT_TOKEN
            else None
        )

    @property
    def enabled(self) -> bool:
        return self._base_url is not None

    def send_recharge_request_message(
        self, chat_id: str, text: str, request_id: str
    ) -> int | None:
        """Returns the sent message_id, or None if sending failed/disabled."""
        if not self.enabled:
            logger.warning("TELEGRAM_BOT_TOKEN not set — skipping direct Telegram notification")
            return None

        try:
            response = httpx.post(
                f"{self._base_url}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "reply_markup": {
                        "inline_keyboard": [[
                            {"text": "✅ Approve", "callback_data": f"rr:approve:{request_id}"},
                            {"text": "❌ Reject", "callback_data": f"rr:reject:{request_id}"},
                        ]]
                    },
                },
                timeout=5,
            )
            response.raise_for_status()
            return response.json()["result"]["message_id"]
        except Exception:
            logger.exception(
                "Failed to send Telegram recharge-request notification to chat_id=%s", chat_id
            )
            return None

    def send_message(self, chat_id: str, text: str) -> None:
        """Plain notification, no inline keyboard — used for low-stock
        inventory alerts."""
        if not self.enabled:
            return

        try:
            response = httpx.post(
                f"{self._base_url}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                timeout=5,
            )
            response.raise_for_status()
        except Exception:
            logger.exception("Failed to send Telegram message to chat_id=%s", chat_id)

    def edit_message(self, chat_id: str, message_id: int, text: str) -> None:
        if not self.enabled:
            return

        try:
            response = httpx.post(
                f"{self._base_url}/editMessageText",
                json={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": text,
                    "parse_mode": "HTML",
                },
                timeout=5,
            )
            response.raise_for_status()
        except Exception:
            logger.exception(
                "Failed to edit Telegram message chat_id=%s message_id=%s", chat_id, message_id
            )


telegram_notifier = TelegramNotifier()
