import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from PIL import Image
from kknova.image_builder import ImageBuilder
from kknova.carousel_generator import InstagramCarouselGenerator

class TestCarouselAndImageBuilder(unittest.TestCase):
    """
    Unit tests for Pillow/Playwright ImageBuilder and InstagramCarouselGenerator in V4.1.
    """
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir_patch = patch("kknova.config.config.BASE_DIR", Path(self.temp_dir.name))
        self.base_dir_patch.start()
        
        self.builder = ImageBuilder()
        self.generator = InstagramCarouselGenerator()
        
        # Build mock report data matching the V4.1 schema
        self.mock_report_data = {
            "scorecard": {
                "market_mood": "Bullish",
                "health_score": 75,
                "fii_vs_dii": "DII Net Buyers",
                "smart_money": "Nifty PSU Bank",
                "risk_level": "Moderate Risk",
                "opportunity_level": "High Opportunity",
                "tomorrow_bias": "Positive",
                "one_line_summary": "Market showed strong buying today on positive global cues."
            },
            "market_health_score": {
                "score": 75,
                "rating": "Healthy",
                "components": {"breadth": 60.0, "momentum": 65.0, "vix": 13.5, "fii_dii_flows": 70.0, "sector_participation": 65.0, "market_strength": 60.0},
                "reasoning": "Strong broad participation was observed today."
            },
            "ai_market_narrative": {
                "what_happened": "Markets rallied today.",
                "why_it_happened": "Global markets were up.",
                "who_drove_the_move": "Institutional buying drove Nifty.",
                "sectors_participating": "Banks led the index higher.",
                "investors_monitor": "US CPI tomorrow."
            },
            "market_breadth": {
                "advances": 1200, "declines": 800, "adr": 1.5, "breadth_score": 60.0,
                "explanation": "Advances were more than declines."
            },
            "fear_greed_analysis": {
                "score": 65, "previous_score": 58, "trend": "Slight greed", "classification": "Greed",
                "explanation": "Greed index rose thoda."
            },
            "india_vix_analysis": {
                "current_vix": 13.5, "daily_change_pct": -4.2, "risk_level": "Low Risk",
                "explanation": "VIX cool off indicates positive trade thoda."
            },
            "fii_dii_intelligence": {
                "fii_net_flow_cr": 450.20, "dii_net_flow_cr": 1200.60,
                "buyer": "DIIs", "seller": "None", "winner": "DIIs", "institutional_strength_score": 82
            },
            "smart_money_tracker": {
                "moving_to": "Banking and IT",
                "exiting_from": "Chemicals",
                "reasoning": "CAPEX allocations support banking index."
            },
            "options_intelligence": {
                "pcr": 1.15, "max_pain": 24000, "highest_call_oi": 24200, "highest_put_oi": 23800,
                "explanation": "Strong put support around 24,000 limits downside."
            },
            "global_market_impact": {
                "sp500": "+0.45%", "nasdaq": "+0.60%", "dow_jones": "+0.20%", "ftse": "+0.15%",
                "dax": "+0.30%", "nikkei": "+0.50%", "hang_seng": "+0.20%", "gift_nifty": "+0.35%",
                "global_impact_score": 75, "explanation": "Strong global cues will push indices higher tomorrow."
            },
            "ipo_intelligence": {
                "status": "No major IPO event impacting market sentiment today."
            },
            "mutual_fund_intelligence": {
                "buying_themes": "Accumulating PSU banks.",
                "selling_themes": "Trimming chemical names.",
                "sector_accumulation": "Infrastructure"
            },
            "sector_rotation_intelligence": {
                "top_performing_sectors": "Nifty PSU Bank, Nifty Infra",
                "top_weak_sectors": "Nifty IT",
                "rotation_reason": "CAPEX allocation support.",
                "narrative": "Smart money rotation is supportive."
            },
            "risks_opportunities": {
                "risks": [
                  { "title": "Global Inflation", "description": "CPI details keep yields high." }
                ],
                "opportunities": [
                  { "title": "Infrastructure spend", "description": "Government spend is strong." }
                ]
            },
            "stocks_to_watch": [
                { "symbol": "SBIN", "trend": "Bullish", "support": 820, "resistance": 860, "reason_to_watch": "Accumulation above daily moving average." }
            ],
            "tomorrow_outlook": {
                "expected_mood": "Bullish Bias",
                "key_support": 23900, "key_resistance": 24200,
                "global_triggers": "US CPI details",
                "institutional_triggers": "FII derivative positions",
                "tomorrow_playbook": "Buy dips near support lines."
            },
            "ai_probability_engine": {
                "bullish_probability": 65, "bearish_probability": 15, "neutral_probability": 20, "ai_confidence_score": 85
            },
            "why_should_i_care": {
                "long_term_investors": "Good accumulation zone.",
                "swing_traders": "Prioritize long trades.",
                "intraday_traders": "Trade range limits.",
                "sip_investors": "Regular monthly allocations.",
                "beginners": "Focus on high-quality index mutual funds."
            },
            "educational_insight": {
                "concept": "VIX measures expected market volatility over the next 30 days."
            },
            "investor_takeaway": {
                "who_benefits": "Value buyers.",
                "who_gets_hurt": "Option buyers.",
                "what_to_watch_next": "Support stability.",
                "one_sentence_summary": "Prioritize capital preservation."
            },
            "data_freshness": {
                "generated_time": "21 Jun 2026 07:45 IST", "market_data_last_updated": "2026-06-21 07:45:00", "freshness_rating": "HIGH"
            },
            "content_quality_score": {
                "score": 92, "coverage_pct": 100, "readability_pct": 95, "data_confidence_pct": 88, "educational_value_pct": 96
            },
            "source_attribution": {
                "sources": ["Yahoo Finance", "NSE India", "BSE India"]
            },
            "kknova_branding": {
                "signature": "KKNova.io Insight",
                "quote": "Markets reward informed decisions.",
                "disclaimer": "Educational Content Only • Not Investment Advice"
            }
        }

    def tearDown(self) -> None:
        self.base_dir_patch.stop()
        self.temp_dir.cleanup()

    def test_image_builder_base_layout(self) -> None:
        """Verify ImageBuilder creates correct dimensions and layouts."""
        img, draw = self.builder.draw_base_layout("Test Header", 1)
        self.assertIsInstance(img, Image.Image)
        self.assertEqual(img.size, (1080, 1350))

    def test_image_builder_build_mood_slide(self) -> None:
        """Verify Slide 1 (Market Mood) builds without raising errors."""
        img = self.builder.build_slide_1_mood(self.mock_report_data)
        self.assertEqual(img.size, (1080, 1350))

    def test_image_builder_build_list_slides(self) -> None:
        """Verify sector list slides build without raising errors."""
        img_strong = self.builder.build_slide_2_strong(self.mock_report_data)
        self.assertEqual(img_strong.size, (1080, 1350))

        img_weak = self.builder.build_slide_3_weak(self.mock_report_data)
        self.assertEqual(img_weak.size, (1080, 1350))

    def test_image_builder_build_stocks_slide(self) -> None:
        """Verify Slide 4 (Stocks To Watch) builds without raising errors."""
        img = self.builder.build_slide_4_stocks(self.mock_report_data)
        self.assertEqual(img.size, (1080, 1350))

    def test_image_builder_build_outlook_slide(self) -> None:
        """Verify Slide 5 (Outlook) builds without raising errors."""
        img = self.builder.build_slide_5_outlook(self.mock_report_data)
        self.assertEqual(img.size, (1080, 1350))

    def test_carousel_parser_standard(self) -> None:
        """Verify JSON report parser successfully extracts all sections."""
        report_json_str = json.dumps(self.mock_report_data)
        data = self.generator.parse_report_text(report_json_str)
        self.assertEqual(data["scorecard"]["market_mood"], "Bullish")
        self.assertEqual(data["scorecard"]["one_line_summary"], "Market showed strong buying today on positive global cues.")

    def test_carousel_package_exports(self) -> None:
        """Verify generated carousel files are successfully saved to directories."""
        report_json_str = json.dumps(self.mock_report_data)
        paths = self.generator.generate_carousel_package(report_json_str)
        
        # Check files exist
        self.assertEqual(len(paths), 8)  # 5 slides + JSON metadata + caption txt + ZIP file
        
        slide_1 = Path(self.temp_dir.name) / "reports" / "carousel_v2" / "slide_1.png"
        json_file = Path(self.temp_dir.name) / "reports" / "carousel_v2" / "carousel_data.json"
        caption_file = Path(self.temp_dir.name) / "reports" / "carousel_v2" / "instagram_caption.txt"
        zip_file = Path(self.temp_dir.name) / "reports" / "carousel_v2" / "kknova_carousel.zip"

        self.assertTrue(slide_1.exists())
        self.assertTrue(json_file.exists())
        self.assertTrue(caption_file.exists())
        self.assertTrue(zip_file.exists())

        # Verify JSON content
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["scorecard"]["market_mood"], "Bullish")

if __name__ == "__main__":
    unittest.main()
