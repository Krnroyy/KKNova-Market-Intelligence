import unittest
import json
from unittest.mock import MagicMock, patch
from kknova.ai_analyst import AIAnalyst

class TestAIAnalyst(unittest.TestCase):
    """
    Unit tests for the AIAnalyst layer, covering JSON schemas and deterministic fallbacks in V4.1.
    """
    def setUp(self) -> None:
        with patch("kknova.config.config.GEMINI_API_KEY", ""):
            self.analyst = AIAnalyst()

    def test_initialization_no_key(self) -> None:
        """Verify that missing API keys disable Gemini and trigger fallback warnings."""
        self.assertFalse(self.analyst.enabled)

    def test_rule_based_fallback_structure(self) -> None:
        """Verify the fallback generator returns a correctly formatted JSON brief matching the schema."""
        market_data = [
            {"symbol": "^NSEI", "current_price": 24000.0, "percentage_change": 0.5, "volume": 1000},
            {"symbol": "^NSEBANK", "current_price": 57000.0, "percentage_change": -0.2, "volume": 500}
        ]
        sector_rankings = [
            ("Nifty PSU Bank", 85.0),
            ("Nifty Auto", 75.0),
            ("Nifty IT", 45.0),
            ("Nifty Pharma", 40.0),
            ("Bank Nifty", 35.0)
        ]
        news_articles = [
            {"category": "Banking", "title": "PSU Banks rally on dividend hopes", "source": "Moneycontrol"}
        ]

        report = self.analyst.analyze_market(market_data, sector_rankings, news_articles)
        
        self.assertIsNotNone(report)
        
        # Verify it parses as JSON and contains required keys
        parsed = json.loads(report)
        self.assertIn("scorecard", parsed)
        self.assertIn("market_health_score", parsed)
        self.assertIn("smart_money_tracker", parsed)
        self.assertIn("stocks_to_watch", parsed)
        self.assertEqual(parsed["scorecard"]["market_mood"], "Bullish")


    @patch("google.generativeai.GenerativeModel")
    @patch("google.generativeai.configure")
    def test_gemini_api_call_success(self, mock_configure, mock_model_class) -> None:
        """Verify that Gemini generates content when API keys are configured."""
        mock_model = MagicMock()
        mock_response = MagicMock()
        
        # Mock Gemini returning a valid JSON string
        dummy_json = {
            "scorecard": {
                "market_mood": "Bullish",
                "health_score": 75,
                "fii_vs_dii": "DII buying",
                "smart_money": "PSU Bank",
                "risk_level": "Low",
                "opportunity_level": "High",
                "tomorrow_bias": "Positive",
                "one_line_summary": "Market close strong thoda."
            },
            "kknova_branding": {
                "signature": "KKNova.io Insight",
                "quote": "Quote",
                "disclaimer": "Disclaimer"
            }
        }
        mock_response.text = json.dumps(dummy_json)
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model

        with patch("kknova.config.config.GEMINI_API_KEY", "dummy-key"):
            analyst = AIAnalyst()
            self.assertTrue(analyst.enabled)
            
            report = analyst.analyze_market([], [], [])
            parsed = json.loads(report)
            self.assertEqual(parsed["scorecard"]["market_mood"], "Bullish")
            self.assertEqual(mock_model.generate_content.call_count, 1)

if __name__ == "__main__":
    unittest.main()
