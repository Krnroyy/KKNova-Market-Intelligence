import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
from pathlib import Path
from kknova.database import DatabaseManager
from kknova.collector import MarketDataCollector

class TestMarketDataCollector(unittest.TestCase):
    """
    Unit tests for the MarketDataCollector, mocking yfinance interactions.
    """
    def setUp(self) -> None:
        self.db_fd, self.db_path_str = tempfile.mkstemp(suffix=".db")
        self.db_path = Path(self.db_path_str)
        self.db = DatabaseManager(self.db_path)
        with self.db as conn:
            conn.initialize_database()
        self.collector = MarketDataCollector(self.db)

    def tearDown(self) -> None:
        os.close(self.db_fd)
        try:
            os.unlink(self.db_path_str)
        except OSError:
            pass

    def test_process_ticker_data_success(self) -> None:
        """Verify successful dataframe processing and computation of price changes."""
        # Create a mock dataframe representing historical day data
        data = {
            "Close": [100.0, 105.0],
            "Volume": [1000, 1200]
        }
        dates = pd.to_datetime(["2026-06-18", "2026-06-19"])
        df = pd.DataFrame(data, index=dates)

        record = self.collector.process_ticker_data("Nifty 50", "^NSEI", df)
        
        self.assertIsNotNone(record)
        self.assertEqual(record["name"], "Nifty 50")
        self.assertEqual(record["symbol"], "^NSEI")
        self.assertEqual(record["current_price"], 105.0)
        self.assertEqual(record["previous_close"], 100.0)
        self.assertEqual(record["percentage_change"], 5.0)
        self.assertEqual(record["volume"], 1200)

    def test_process_ticker_data_missing_volume(self) -> None:
        """Verify processing of tickers that don't report volume (e.g. some indices)."""
        data = {
            "Close": [200.0, 198.0]
        }
        dates = pd.to_datetime(["2026-06-18", "2026-06-19"])
        df = pd.DataFrame(data, index=dates)

        record = self.collector.process_ticker_data("Nifty IT", "^CNXIT", df)
        
        self.assertIsNotNone(record)
        self.assertEqual(record["current_price"], 198.0)
        self.assertEqual(record["previous_close"], 200.0)
        self.assertEqual(record["percentage_change"], -1.0)
        self.assertEqual(record["volume"], 0)

    def test_process_ticker_data_insufficient_rows(self) -> None:
        """Verify handling of dataframes with insufficient history (fewer than 2 rows)."""
        data = {
            "Close": [100.0]
        }
        dates = pd.to_datetime(["2026-06-19"])
        df = pd.DataFrame(data, index=dates)

        record = self.collector.process_ticker_data("Nifty 50", "^NSEI", df)
        self.assertIsNone(record)

    @patch("yfinance.Ticker")
    def test_fetch_ticker_data_with_retry_success(self, mock_ticker_class) -> None:
        """Verify that fetch succeeds on normal response."""
        mock_ticker = MagicMock()
        mock_df = pd.DataFrame({"Close": [100.0, 102.0]})
        mock_ticker.history.return_value = mock_df
        mock_ticker_class.return_value = mock_ticker

        res_df = self.collector.fetch_ticker_data_with_retry("^NSEI")
        self.assertIsNotNone(res_df)
        self.assertFalse(res_df.empty)
        self.assertEqual(res_df["Close"].iloc[1], 102.0)

    @patch("yfinance.Ticker")
    @patch("time.sleep") # Mock sleep to speed up test execution
    def test_fetch_ticker_data_retry_on_failure(self, mock_sleep, mock_ticker_class) -> None:
        """Verify retry and backoff are triggered when API calls fail."""
        mock_ticker = MagicMock()
        # Raise an exception when history is called
        mock_ticker.history.side_effect = Exception("API rate limited")
        mock_ticker_class.return_value = mock_ticker

        res_df = self.collector.fetch_ticker_data_with_retry("^NSEI")
        self.assertIsNone(res_df)
        # Verify that history was called config.RETRY_COUNT times (default: 3)
        self.assertEqual(mock_ticker.history.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)  # Sleeping after attempt 1 and 2

if __name__ == "__main__":
    unittest.main()
