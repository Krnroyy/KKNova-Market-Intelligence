import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from kknova.database import DatabaseManager
from kknova.sentiment_preprocessor import SentimentPreprocessor
from kknova.news_collector import NewsCollector

class TestNewsModules(unittest.TestCase):
    """
    Unit tests for SentimentPreprocessor and NewsCollector modules.
    """
    def setUp(self) -> None:
        # Temporary DB file on disk for database operations
        self.db_fd, self.db_path_str = tempfile.mkstemp(suffix=".db")
        self.db = DatabaseManager(Path(self.db_path_str))
        with self.db as conn:
            conn.initialize_database()
        self.collector = NewsCollector(self.db)
        self.preprocessor = SentimentPreprocessor()

    def tearDown(self) -> None:
        os.close(self.db_fd)
        try:
            os.unlink(self.db_path_str)
        except OSError:
            pass

    def test_clean_text(self) -> None:
        """Verify HTML unescaping, lowercase conversion, and whitespace cleaning."""
        raw_headline = "  TCS &amp; Infosys announce &lt;strong&gt;Q4 results&lt;/strong&gt;   "
        expected = "tcs & infosys announce q4 results"
        self.assertEqual(self.preprocessor.clean_text(raw_headline), expected)

    def test_classify_text_by_sector(self) -> None:
        """Verify keyword classification maps headlines to correct sectors."""
        # Banking
        self.assertEqual(self.preprocessor.classify_text("SBI reports lower NPA in Q4"), "Banking")
        # IT
        self.assertEqual(self.preprocessor.classify_text("Infosys signs new $2B software deal"), "IT")
        # Auto
        self.assertEqual(self.preprocessor.classify_text("Tata Motors EV sales jump 50 percent"), "Auto")
        # Defence
        self.assertEqual(self.preprocessor.classify_text("HAL gets order for light combat aircraft"), "Defence")
        # Renewable Energy
        self.assertEqual(self.preprocessor.classify_text("Green energy transition: Solar panel tariffs cut"), "Renewable Energy")
        # No matches
        self.assertEqual(self.preprocessor.classify_text("Tomato prices surge across wholesale markets"), "General")

    @patch("requests.get")
    def test_fetch_rss_feed_parsing(self, mock_get) -> None:
        """Verify XML parsing of standard RSS items."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Mock News Channel</title>
                <item>
                    <title>Wipro shares buzzing in early trade</title>
                    <link>https://example.com/wipro-news</link>
                    <pubDate>Sat, 20 Jun 2026 10:00:00 GMT</pubDate>
                </item>
                <item>
                    <title>BHEL receives huge boiler order from NTPC</title>
                    <link>https://example.com/bhel-news</link>
                    <pubDate>Sat, 20 Jun 2026 11:30:00 GMT</pubDate>
                </item>
            </channel>
        </rss>
        """
        mock_get.return_value = mock_response

        articles = self.collector.fetch_rss_feed("MockSource", "https://example.com/rss")
        
        self.assertEqual(len(articles), 2)
        self.assertEqual(articles[0]["title"], "Wipro shares buzzing in early trade")
        self.assertEqual(articles[0]["url"], "https://example.com/wipro-news")
        self.assertEqual(articles[0]["source"], "MockSource")
        self.assertEqual(articles[1]["title"], "BHEL receives huge boiler order from NTPC")

    @patch("requests.get")
    def test_fetch_news_api_parsing(self, mock_get) -> None:
        """Verify NewsAPI JSON response parsing."""
        # Set dummy key for testing NewsAPI flow
        with patch("kknova.config.config.NEWS_API_KEY", "dummy-key"):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "articles": [
                    {
                        "title": "Government pushes for local solar panel manufacturing",
                        "url": "https://example.com/solar-panels",
                        "publishedAt": "2026-06-20T08:00:00Z",
                        "source": {"name": "Economic Times"}
                    }
                ]
            }
            mock_get.return_value = mock_response

            articles = self.collector.fetch_news_api("Renewable Energy")
            
            self.assertEqual(len(articles), 1)
            self.assertEqual(articles[0]["title"], "Government pushes for local solar panel manufacturing")
            self.assertEqual(articles[0]["url"], "https://example.com/solar-panels")
            self.assertEqual(articles[0]["source"], "Economic Times")

    def test_news_deduplication(self) -> None:
        """Verify duplicate URLs are filtered out by database UNIQUE constraints."""
        timestamp = "2026-06-20T12:00:00"
        title1 = "HDFC Bank Q4 profits rise 20%"
        title2 = "HDFC Bank profits jump 20%"
        url = "https://example.com/hdfc-q4"

        # First insert
        with self.db as conn:
            success1 = conn.insert_news_article(timestamp, title1, "SourceA", url, "2026-06-20", "Banking")
            # Second insert with same URL
            success2 = conn.insert_news_article(timestamp, title2, "SourceB", url, "2026-06-20", "Banking")

        self.assertTrue(success1)
        self.assertTrue(success2)  # sqlite insert returns True but executes OR IGNORE

        # Verify only one entry exists in database
        with self.db as conn:
            cursor = conn._execute("SELECT * FROM news_data WHERE url = ?", (url,))
            rows = cursor.fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["title"], title1)  # Keeps the first inserted title
            self.assertEqual(rows[0]["source"], "SourceA")

if __name__ == "__main__":
    unittest.main()
