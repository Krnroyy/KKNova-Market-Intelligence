import os
import tempfile
import unittest
from pathlib import Path
from kknova.database import DatabaseManager

class TestDatabaseManager(unittest.TestCase):
    """
    Unit tests for the DatabaseManager class using a temporary database on disk.
    """
    def setUp(self) -> None:
        self.db_fd, self.db_path_str = tempfile.mkstemp(suffix=".db")
        self.db_path = Path(self.db_path_str)
        self.db = DatabaseManager(self.db_path)
        # Initialize tables
        with self.db as conn:
            conn.initialize_database()

    def tearDown(self) -> None:
        os.close(self.db_fd)
        try:
            os.unlink(self.db_path_str)
        except OSError:
            pass

    def test_table_creation(self) -> None:
        """Verify that all required tables and indexes are created successfully."""
        with self.db as conn:
            cursor = conn._execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('market_data', 'sector_data', 'reports', 'logs')"
            )
            tables = [row[0] for row in cursor.fetchall()]
            
            self.assertIn("market_data", tables)
            self.assertIn("sector_data", tables)
            self.assertIn("reports", tables)
            self.assertIn("logs", tables)

    def test_insert_and_get_market_data(self) -> None:
        """Verify insertion and retrieval of broad market data records."""
        with self.db as conn:
            # Insert test record
            success = conn.insert_market_data(
                timestamp="2026-06-20T12:00:00",
                symbol="^NSEI",
                current_price=23500.50,
                previous_close=23400.00,
                percentage_change=0.43,
                volume=1500000
            )
            self.assertTrue(success)

            # Retrieve records
            records = conn.get_latest_market_data()
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["symbol"], "^NSEI")
            self.assertEqual(records[0]["current_price"], 23500.50)
            self.assertEqual(records[0]["percentage_change"], 0.43)
            self.assertEqual(records[0]["volume"], 1500000)

    def test_insert_and_get_sector_data(self) -> None:
        """Verify insertion and retrieval of sector data records."""
        with self.db as conn:
            # Insert test record
            success = conn.insert_sector_data(
                timestamp="2026-06-20T12:00:00",
                symbol="^CNXIT",
                sector_name="Nifty IT",
                current_price=35000.25,
                previous_close=34800.00,
                percentage_change=0.58,
                volume=800000
            )
            self.assertTrue(success)

            # Retrieve records
            records = conn.get_latest_sector_data()
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["symbol"], "^CNXIT")
            self.assertEqual(records[0]["sector_name"], "Nifty IT")
            self.assertEqual(records[0]["current_price"], 35000.25)
            self.assertEqual(records[0]["percentage_change"], 0.58)

    def test_insert_report(self) -> None:
        """Verify insertion of reports."""
        with self.db as conn:
            success = conn.insert_report(
                timestamp="2026-06-20T12:00:00",
                report_type="Daily EOD",
                content="Daily EOD analysis for Instagram post.",
                status="DRAFT"
            )
            self.assertTrue(success)

            # Validate directly in the DB
            cursor = conn._execute("SELECT * FROM reports")
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["report_type"], "Daily EOD")
            self.assertEqual(row["status"], "DRAFT")

    def test_duplicate_prevention(self) -> None:
        """Verify that UNIQUE constraints prevent duplicate inserts and replace them."""
        with self.db as conn:
            timestamp = "2026-06-20T12:00:00"
            symbol = "^NSEI"

            # Insert first
            conn.insert_market_data(timestamp, symbol, 100.0, 95.0, 5.26, 1000)
            # Insert second with modified values for same key (timestamp, symbol)
            conn.insert_market_data(timestamp, symbol, 105.0, 95.0, 10.53, 1200)

            # Check db contains only one row, and it contains the updated value
            records = conn.get_latest_market_data()
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["current_price"], 105.0)
            self.assertEqual(records[0]["volume"], 1200)

    def test_portfolio_crud(self) -> None:
        """Verify insertion, retrieval, and deletion of portfolio holdings."""
        with self.db as conn:
            # Insert holdings
            success = conn.insert_portfolio_holding("2026-06-20", "RELIANCE.NS", 10.0, 2400.0, "Nifty Energy")
            self.assertTrue(success)
            success = conn.insert_portfolio_holding("2026-06-20", "TCS.NS", 5.0, 3800.0, "Nifty IT")
            self.assertTrue(success)

            # Retrieve holdings
            holdings = conn.get_portfolio_holdings()
            self.assertEqual(len(holdings), 2)
            self.assertEqual(holdings[0]["symbol"], "RELIANCE.NS")
            self.assertEqual(holdings[1]["symbol"], "TCS.NS")

            # Update holding (replace UNIQUE symbol)
            success = conn.insert_portfolio_holding("2026-06-20", "RELIANCE.NS", 12.0, 2450.0, "Nifty Energy")
            self.assertTrue(success)
            holdings = conn.get_portfolio_holdings()
            self.assertEqual(len(holdings), 2)
            self.assertEqual(holdings[0]["shares"], 12.0)
            self.assertEqual(holdings[0]["buy_price"], 2450.0)

            # Delete holding
            success = conn.delete_portfolio_holding("TCS.NS")
            self.assertTrue(success)
            holdings = conn.get_portfolio_holdings()
            self.assertEqual(len(holdings), 1)
            self.assertEqual(holdings[0]["symbol"], "RELIANCE.NS")

    def test_watchlist_crud(self) -> None:
        """Verify watchlist CRUD helper methods."""
        with self.db as conn:
            # Insert watchlist items
            self.assertTrue(conn.insert_watchlist_item("2026-06-20", "Growth", "INFY.NS"))
            self.assertTrue(conn.insert_watchlist_item("2026-06-20", "Growth", "SBI.NS"))
            self.assertTrue(conn.insert_watchlist_item("2026-06-20", "Defensive", "ITC.NS"))

            # Retrieve names
            names = conn.get_watchlist_names()
            self.assertEqual(names, ["Defensive", "Growth"])

            # Retrieve items
            growth_items = conn.get_watchlist_items("Growth")
            self.assertEqual(len(growth_items), 2)
            self.assertEqual(growth_items[0]["symbol"], "INFY.NS")
            self.assertEqual(growth_items[1]["symbol"], "SBI.NS")

            # Delete item
            self.assertTrue(conn.delete_watchlist_item("Growth", "SBI.NS"))
            growth_items = conn.get_watchlist_items("Growth")
            self.assertEqual(len(growth_items), 1)
            self.assertEqual(growth_items[0]["symbol"], "INFY.NS")

            # Delete watchlist
            self.assertTrue(conn.delete_watchlist("Growth"))
            self.assertEqual(conn.get_watchlist_names(), ["Defensive"])


if __name__ == "__main__":
    unittest.main()
