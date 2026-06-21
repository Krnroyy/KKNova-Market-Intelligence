import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from kknova.database import DatabaseManager
from kknova.sector_strength_engine import SectorStrengthEngine

class TestSectorStrengthEngine(unittest.TestCase):
    """
    Unit tests for the SectorStrengthEngine, including scoring and normalization calculations.
    """
    def setUp(self) -> None:
        self.db_fd, self.db_path_str = tempfile.mkstemp(suffix=".db")
        self.db = DatabaseManager(Path(self.db_path_str))
        with self.db as conn:
            conn.initialize_database()
        self.engine = SectorStrengthEngine(self.db)

    def tearDown(self) -> None:
        os.close(self.db_fd)
        try:
            os.unlink(self.db_path_str)
        except OSError:
            pass

    def test_normalize_list_normal_range(self) -> None:
        """Verify standard Min-Max scaling normalizes inputs between 0 and 100."""
        inputs = [10.0, 20.0, 30.0, 50.0]
        # 10 maps to 0, 50 maps to 100, 20 maps to 100*(20-10)/(50-10) = 25.0
        expected = [0.0, 25.0, 50.0, 100.0]
        normalized = self.engine._normalize_list(inputs)
        self.assertEqual(normalized, expected)

    def test_normalize_list_equal_values(self) -> None:
        """Verify min-max scaling defaults to 50 when all values are equal."""
        inputs = [15.0, 15.0, 15.0]
        expected = [50.0, 50.0, 50.0]
        normalized = self.engine._normalize_list(inputs)
        self.assertEqual(normalized, expected)

    def test_calculate_scores_computation(self) -> None:
        """Verify weighted scoring is calculated correctly based on the formula weights."""
        # 40% Price Performance, 20% Volume Strength, 20% Relative Strength, 20% News Activity
        raw_data = {
            "Nifty IT": {
                "price_performance": 1.0,  # min price
                "volume_strength": 1.0,    # min volume
                "relative_strength": 0.0,  # min rel strength
                "news_activity": 0.0       # min news
            },
            "Nifty Auto": {
                "price_performance": 3.0,  # max price
                "volume_strength": 2.0,    # max volume
                "relative_strength": 2.0,  # max rel strength
                "news_activity": 10.0      # max news
            }
        }
        
        # In Min-Max scaling:
        # Nifty IT: price=0, volume=0, rel=0, news=0 -> Final Score = 0
        # Nifty Auto: price=100, volume=100, rel=100, news=100 -> Final Score = 100
        scores = self.engine.calculate_scores(raw_data)
        
        self.assertEqual(len(scores), 2)
        self.assertEqual(scores[0], ("Nifty Auto", 100.0))
        self.assertEqual(scores[1], ("Nifty IT", 0.0))

    @patch("kknova.database.DatabaseManager.get_latest_market_data_for_symbol")
    @patch("kknova.database.DatabaseManager.get_latest_sector_data_for_symbol")
    @patch("kknova.database.DatabaseManager.get_historical_sector_volumes")
    @patch("kknova.database.DatabaseManager.get_news_count_by_category")
    def test_run_engine_pipeline(
        self,
        mock_news,
        mock_volumes,
        mock_sector_quote,
        mock_market_quote
    ) -> None:
        """Verify that the engine runs, calculates ranks, and commits records to SQLite."""
        # Setup mocks
        # Nifty 50 daily change benchmark
        mock_market_quote.side_effect = lambda symbol: (
            {"percentage_change": 1.0, "volume": 100000} if symbol == "^NSEI"
            else {"percentage_change": 2.0, "volume": 50000}  # Bank Nifty
        )
        
        # Sector quotes
        mock_sector_quote.side_effect = lambda symbol: {
            "^NSEBANK": {"percentage_change": 2.0, "volume": 50000},
            "^CNXFIN": {"percentage_change": 1.2, "volume": 25000},
            "^CNXIT": {"percentage_change": -1.0, "volume": 20000},
            "^CNXAUTO": {"percentage_change": 0.0, "volume": 10000},
            "^CNXPHARMA": {"percentage_change": 1.5, "volume": 15000},
            "^CNXFMCG": {"percentage_change": 0.5, "volume": 12000},
            "^CNXREALTY": {"percentage_change": 1.8, "volume": 8000},
            "^CNXMETAL": {"percentage_change": -0.5, "volume": 18000},
            "^CNXENERGY": {"percentage_change": 0.7, "volume": 22000},
            "^CNXPSUBANK": {"percentage_change": 3.0, "volume": 30000},
            "^CNXINFRA": {"percentage_change": 1.0, "volume": 14000}
        }.get(symbol, {"percentage_change": 0.0, "volume": 10000})

        # Volumes history (return current and prev volume to compute volume ratio)
        mock_volumes.side_effect = lambda symbol, limit: {
            "^NSEBANK": [50000, 50000],
            "^CNXFIN": [25000, 25000],
            "^CNXIT": [20000, 10000],    # ratio = 2.0
            "^CNXAUTO": [10000, 10000],  # ratio = 1.0
            "^CNXPHARMA": [15000, 15000],# ratio = 1.0
            "^CNXFMCG": [12000, 12000],
            "^CNXREALTY": [8000, 8000],
            "^CNXMETAL": [18000, 18000],
            "^CNXENERGY": [22000, 22000],
            "^CNXPSUBANK": [30000, 10000], # ratio = 3.0
            "^CNXINFRA": [14000, 14000]
        }.get(symbol, [10000, 10000])

        # News counts in last 24h
        mock_news.side_effect = lambda category, since: {
            "Banking": 5,
            "Finance": 3,
            "IT": 2,
            "Auto": 0,
            "Pharma": 4,
            "FMCG": 1,
            "Realty": 2,
            "Metal": 1,
            "Energy": 2,
            "PSU": 10,
            "Infrastructure": 2
        }.get(category, 0)

        # Run engine
        rankings = self.engine.run_engine()
        
        self.assertEqual(len(rankings), 11)
        # Check sorting order
        self.assertTrue(rankings[0][1] >= rankings[1][1] >= rankings[2][1])
        
        # Verify database has ranking rows
        with self.db as conn:
            cursor = conn._execute("SELECT * FROM sector_rankings ORDER BY rank ASC")
            db_ranks = cursor.fetchall()
            self.assertEqual(len(db_ranks), 11)
            self.assertEqual(db_ranks[0]["rank"], 1)
            self.assertEqual(db_ranks[0]["sector_name"], rankings[0][0])
            self.assertEqual(db_ranks[0]["score"], rankings[0][1])

if __name__ == "__main__":
    unittest.main()
