import asyncio
import os
import time
import random
import telegram
from pathlib import Path
from kknova.config import config
from kknova.logger import logger

class TelegramSender:
    """
    Publishes market briefs to a Telegram Channel or Group.
    Implements retries with backoff and saves reports to a local file if keys are missing.
    """
    def __init__(self) -> None:
        self.bot_token = config.TELEGRAM_BOT_TOKEN
        self.chat_id = config.TELEGRAM_CHAT_ID
        self.enabled = bool(self.bot_token and self.chat_id)
        if not self.enabled:
            logger.warning("Telegram Bot Token or Chat ID not configured. Reports will fall back to local disk files.")

    async def _send_message_async(self, text: str) -> None:
        """Sends the text using the asynchronous python-telegram-bot API."""
        bot = telegram.Bot(token=self.bot_token)
        # Using markdown formatting or HTML if needed, defaulting to plain text parsing for maximum safety
        await bot.send_message(chat_id=self.chat_id, text=text)

    def send_report(self, report_content: str) -> bool:
        """
        Orchestrates publishing the brief.
        If disabled, writes the brief locally to reports/latest_telegram_brief.txt.
        If enabled, tries to publish with exponential backoff and logs outcome.
        """
        if not self.enabled:
            logger.info("Telegram integration is disabled. Outputting report to local disk.")
            return self._write_to_file(report_content)

        retries = 0
        max_retries = config.RETRY_COUNT
        backoff_factor = config.RETRY_BACKOFF

        while retries < max_retries:
            try:
                logger.info(f"Sending brief to Telegram (Attempt {retries + 1}/{max_retries})...")
                # Run the async helper in the current thread's loop
                asyncio.run(self._send_message_async(report_content))
                logger.info("Successfully sent brief to Telegram.")
                # Keep a local copy as backup
                self._write_to_file(report_content)
                return True
            except Exception as e:
                retries += 1
                logger.warning(
                    f"Attempt {retries} failed to send Telegram message: {e}. "
                    f"Retrying..."
                )
                if retries >= max_retries:
                    logger.error(f"Failed to send Telegram message after {max_retries} attempts. Saving locally.")
                    self._write_to_file(report_content)
                    return False
                
                sleep_time = (backoff_factor ** retries) + random.uniform(0.1, 1.0)
                time.sleep(sleep_time)
        return False

    def _write_to_file(self, report_content: str) -> bool:
        """Helper to save a backup or offline copy of the report to the reports folder."""
        try:
            reports_dir = config.BASE_DIR / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            report_file = reports_dir / "latest_telegram_brief.txt"
            with open(report_file, "w", encoding="utf-8") as f:
                f.write(report_content)
            logger.info(f"Market brief saved locally to: {report_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to write offline copy of report: {e}")
            return False
