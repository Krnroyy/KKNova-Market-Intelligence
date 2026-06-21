import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from kknova.config import config
from kknova.telegram_sender import TelegramSender

class TestTelegramSender(unittest.TestCase):
    """
    Unit tests for the TelegramSender module.
    """
    def setUp(self) -> None:
        # Patch BASE_DIR in config to use a temporary directory for test report files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir_patch = patch("kknova.config.config.BASE_DIR", Path(self.temp_dir.name))
        self.base_dir_patch.start()
        
        # Instantiate disabled sender (default since no keys in test execution env)
        with patch("kknova.config.config.TELEGRAM_BOT_TOKEN", ""), patch("kknova.config.config.TELEGRAM_CHAT_ID", ""):
            self.sender = TelegramSender()

    def tearDown(self) -> None:
        self.base_dir_patch.stop()
        self.temp_dir.cleanup()

    def test_disabled_by_default(self) -> None:
        """Verify sender is disabled when environment keys are missing."""
        self.assertFalse(self.sender.enabled)

    def test_offline_fallback_file_creation(self) -> None:
        """Verify disabled sender falls back to writing report briefs locally to disk."""
        brief = "🚀 KKNova Market Brief\nMarket Mood: Neutral"
        success = self.sender.send_report(brief)
        
        self.assertTrue(success)
        
        # Verify file exists and has correct content
        expected_file = Path(self.temp_dir.name) / "reports" / "latest_telegram_brief.txt"
        self.assertTrue(expected_file.exists())
        with open(expected_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertEqual(content, brief)

    @patch("telegram.Bot.send_message")
    def test_telegram_send_success(self, mock_send_message) -> None:
        """Verify successful Telegram dispatch when environment variables are set."""
        # Define async dummy mock for telegram API
        async def dummy_async(*args, **kwargs):
            return True
        mock_send_message.side_effect = dummy_async

        with patch("kknova.config.config.TELEGRAM_BOT_TOKEN", "dummy-token"), patch("kknova.config.config.TELEGRAM_CHAT_ID", "dummy-chat-id"):
            sender = TelegramSender()
            self.assertTrue(sender.enabled)
            
            success = sender.send_report("Hello Telegram!")
            self.assertTrue(success)
            self.assertEqual(mock_send_message.call_count, 1)

    @patch("telegram.Bot.send_message")
    @patch("time.sleep") # Mock sleep to speed up test execution
    def test_telegram_retry_on_network_failure(self, mock_sleep, mock_send_message) -> None:
        """Verify that telegram sender retries on network/API failure and defaults to local save."""
        # Make the async send fail
        async def dummy_async_fail(*args, **kwargs):
            raise Exception("Telegram Connection Timeout")
        mock_send_message.side_effect = dummy_async_fail

        with patch("kknova.config.config.TELEGRAM_BOT_TOKEN", "dummy-token"), patch("kknova.config.config.TELEGRAM_CHAT_ID", "dummy-chat-id"):
            sender = TelegramSender()
            
            success = sender.send_report("Retry Test")
            # Should fail telegram but return True because it successfully saved to file as fallback
            self.assertFalse(success)  # Returns False since Telegram call failed after all retries
            self.assertEqual(mock_send_message.call_count, config.RETRY_COUNT)
            self.assertEqual(mock_sleep.call_count, config.RETRY_COUNT - 1)
            
            # Check local fallback file still generated
            expected_file = Path(self.temp_dir.name) / "reports" / "latest_telegram_brief.txt"
            self.assertTrue(expected_file.exists())

if __name__ == "__main__":
    unittest.main()
