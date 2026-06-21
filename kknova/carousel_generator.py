import json
import logging
import zipfile
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from kknova.config import config
from kknova.logger import logger
from kknova.image_builder import ImageBuilder

class InstagramCarouselGenerator:
    """
    Parses market briefs (JSON) and coordinates V4.1 slide generation,
    exporting slides (PNGs), metadata (JSON), captions (TXT), and bundling as a ZIP.
    """
    def __init__(self) -> None:
        self.image_builder = ImageBuilder()
        self.output_dir = config.BASE_DIR / "reports" / "carousel_v2"

    def parse_report_text(self, text: str) -> Dict[str, Any]:
        """
        Loads report JSON directly and runs structural schema validation.
        """
        default_data = {
            "scorecard": {
                "market_mood": "Neutral",
                "health_score": 55,
                "fii_vs_dii": "DII Net Buyers",
                "smart_money": "Nifty PSU Bank",
                "risk_level": "Moderate Risk",
                "opportunity_level": "Moderate Opportunity",
                "tomorrow_bias": "Neutral",
                "one_line_summary": "Market thoda rangebound tha due to persistent FII profit booking."
            },
            "market_health_score": {
                "score": 55,
                "rating": "Neutral",
                "components": {"breadth": 50.0, "momentum": 50.0, "vix": 14.5, "fii_dii_flows": 60.0, "sector_participation": 55.0, "market_strength": 50.0},
                "reasoning": "Consolidation pattern thoda continue ho raha hai."
            },
            "ai_market_narrative": {
                "what_happened": "Indices closed flat today after minor volatility.",
                "why_it_happened": "Absence of strong global direction kept traders on sideline.",
                "who_drove_the_move": "FII flow was offset by steady DII buying.",
                "sectors_participating": "PSU Banks and Realty led, while IT slipped thoda down.",
                "investors_monitor": "US bond yields and Brent crude prices."
            },
            "market_breadth": {
                "advances": 980, "declines": 1120, "adr": 0.87, "breadth_score": 46.5,
                "explanation": "More stocks declined than advanced, indicating minor retail selling."
            },
            "fear_greed_analysis": {
                "score": 45, "previous_score": 49, "trend": "Slide to fear", "classification": "Neutral",
                "explanation": "Traders are cautious close to daily support zones."
            },
            "india_vix_analysis": {
                "current_vix": 14.52, "daily_change_pct": 2.15, "risk_level": "Moderate Risk",
                "explanation": "VIX range bound index shows that major panics are not expected."
            },
            "fii_dii_intelligence": {
                "fii_net_flow_cr": -1450.20, "dii_net_flow_cr": 1920.60,
                "buyer": "DIIs", "seller": "FIIs", "winner": "DIIs", "institutional_strength_score": 68
            },
            "smart_money_tracker": {
                "moving_to": "Banking and Realty",
                "exiting_from": "Information Technology (IT) and Metal",
                "reasoning": "Capital is rotating into sectors showing strong local CAPEX demand."
            },
            "options_intelligence": {
                "pcr": 0.94, "max_pain": 24000, "highest_call_oi": 24200, "highest_put_oi": 23800,
                "explanation": "Call writing observed around the 24,200 strike limits."
            },
            "global_market_impact": {
                "sp500": "-0.28%", "nasdaq": "-0.75%", "dow_jones": "+0.08%", "ftse": "-0.15%",
                "dax": "-0.22%", "nikkei": "-0.45%", "hang_seng": "-0.32%", "gift_nifty": "-0.18%",
                "global_impact_score": 42, "explanation": "Weak tech cues will thoda drag Nifty IT shares tomorrow."
            },
            "ipo_intelligence": {
                "status": "No major IPO event impacting market sentiment today."
            },
            "mutual_fund_intelligence": {
                "buying_themes": "Accumulating PSU banks and capital goods shares.",
                "selling_themes": "Trimming chemical names.",
                "sector_accumulation": "Infrastructure and Power Utilities"
            },
            "sector_rotation_intelligence": {
                "top_performing_sectors": "Nifty Realty, Nifty PSU Bank",
                "top_weak_sectors": "Nifty IT, Nifty Metal",
                "rotation_reason": "CAPEX allocations support local capital goods sector.",
                "narrative": "Rotation shows structural strength in domestic cyclicals."
            },
            "risks_opportunities": {
                "risks": [
                  { "title": "FII outflows", "description": "Global yields are pulling capital thoda slow." },
                  { "title": "IT Earnings slowdown", "description": "Tech spending delays keep upside limited." }
                ],
                "opportunities": [
                  { "title": "Local infrastructure spend", "description": "Government CAPEX plans offer long term earnings visibility." },
                  { "title": "Defensive rotation", "description": "Utilities and pharma sectors offer stable dividends." }
                ]
            },
            "stocks_to_watch": [
                { "symbol": "SBIN", "trend": "Bullish", "support": 820, "resistance": 860, "reason_to_watch": "Showing accumulation above key daily moving averages." },
                { "symbol": "TCS", "trend": "Bearish", "support": 3810, "resistance": 3940, "reason_to_watch": "Under pressure due to weak Nasdaq flows." },
                { "symbol": "HAL", "trend": "Neutral", "support": 4250, "resistance": 4450, "reason_to_watch": "Consolidating inside a tight range, watch breakouts." }
            ],
            "tomorrow_outlook": {
                "expected_mood": "Cautious Rangebound",
                "key_support": 23900, "key_resistance": 24200,
                "global_triggers": "US CPI details and crude pricing",
                "institutional_triggers": "FII derivative positions",
                "tomorrow_playbook": "Watch opening 15-min range boundaries. Trade only post trend confirmation."
            },
            "ai_probability_engine": {
                "bullish_probability": 35, "bearish_probability": 45, "neutral_probability": 20, "ai_confidence_score": 90
            },
            "why_should_i_care": {
                "long_term_investors": "Good accumulation zone for quality large-caps on dips.",
                "swing_traders": "Prioritize long trades in high-momentum sectors.",
                "intraday_traders": "Trade range limits near supports, do not chase early gaps.",
                "sip_investors": "Consolidation allows SIPs to acquire optimal units.",
                "beginners": "Focus on high-quality index mutual funds instead of small-caps."
            },
            "educational_insight": {
                "concept": "VIX measures expected market volatility over the next 30 days. Higher VIX indicates higher risk."
            },
            "investor_takeaway": {
                "who_benefits": "Value buyers adding cyclical industrial counters.",
                "who_gets_hurt": "Option buyers holding overnight positions in volatile sessions.",
                "what_to_watch_next": "Support stability near Nifty 50 intermediate levels.",
                "one_sentence_summary": "Prioritize capital preservation during ranges."
            },
            "data_freshness": {
                "generated_time": "21 Jun 2026 07:45 IST", "market_data_last_updated": "2026-06-21 07:45:00", "freshness_rating": "HIGH"
            },
            "content_quality_score": {
                "score": 92, "coverage_pct": 100, "readability_pct": 95, "data_confidence_pct": 88, "educational_value_pct": 96
            },
            "source_attribution": {
                "sources": ["Yahoo Finance", "NSE India", "BSE India", "RSS News Feeds", "SEBI"]
            },
            "kknova_branding": {
                "signature": "KKNova.io Insight",
                "quote": "Markets reward informed decisions, not emotional reactions.",
                "disclaimer": "Educational Content Only • Not Investment Advice"
            }
        }

        if not text:
            return default_data

        try:
            parsed = json.loads(text)
            
            # JSON Schema Structural Guardrail Validation
            mandatory_top_keys = [
                "scorecard", "market_health_score", "ai_market_narrative", "market_breadth", 
                "fear_greed_analysis", "india_vix_analysis", "fii_dii_intelligence", 
                "smart_money_tracker", "options_intelligence", "global_market_impact", 
                "ipo_intelligence", "mutual_fund_intelligence", "sector_rotation_intelligence", 
                "risks_opportunities", "stocks_to_watch", "tomorrow_outlook", 
                "ai_probability_engine", "why_should_i_care", "educational_insight", 
                "investor_takeaway", "data_freshness", "content_quality_score", 
                "source_attribution", "kknova_branding"
            ]
            
            # Verify and merge with defaults if keys are missing
            for key in mandatory_top_keys:
                if key not in parsed:
                    parsed[key] = default_data[key]
                    logger.warning(f"JSON validation warning: missing key '{key}' merged from default cache.")
                    
            return parsed
        except Exception as e:
            logger.error(f"JSON parsing/schema validation failed: {e}. Reverting to default report dictionary.")
            return default_data

    def generate_carousel_package(self, report_text: str) -> List[Path]:
        """
        Coordinates parsing, builds 5 slide images, creates the JSON metadata,
        writes the TXT caption copy, bundles all files into a ZIP archive, and returns file paths.
        """
        logger.info("Initializing Instagram Carousel generation...")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. Parse report JSON content and validate
        parsed = self.parse_report_text(report_text)

        # 2. Build Slide Images
        generated_paths: List[Path] = []
        try:
            # Slide 1: Market In 10 Seconds
            img1 = self.image_builder.build_slide_1_mood(parsed)
            path1 = self.output_dir / "slide_1.png"
            img1.save(path1)
            generated_paths.append(path1)

            # Slide 2: Where Smart Money Is Moving
            img2 = self.image_builder.build_slide_2_strong(parsed)
            path2 = self.output_dir / "slide_2.png"
            img2.save(path2)
            generated_paths.append(path2)

            # Slide 3: Risks & Opportunities
            img3 = self.image_builder.build_slide_3_weak(parsed)
            path3 = self.output_dir / "slide_3.png"
            img3.save(path3)
            generated_paths.append(path3)

            # Slide 4: Tomorrow Levels & Options Data
            img4 = self.image_builder.build_slide_4_stocks(parsed)
            path4 = self.output_dir / "slide_4.png"
            img4.save(path4)
            generated_paths.append(path4)

            # Slide 5: AI Outlook + Takeaway
            img5 = self.image_builder.build_slide_5_outlook(parsed)
            path5 = self.output_dir / "slide_5.png"
            img5.save(path5)
            generated_paths.append(path5)
            
            logger.info(f"Successfully generated 5 PNG slides under {self.output_dir}")
        except Exception as e:
            logger.error(f"Error rendering slide images: {e}", exc_info=True)
            raise

        # 3. Export JSON Metadata for future Canva ingestion
        json_path = self.output_dir / "carousel_data.json"
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(parsed, f, indent=4)
            logger.info(f"Saved Canva-ready JSON metadata: {json_path}")
            generated_paths.append(json_path)
        except Exception as e:
            logger.error(f"Failed to write JSON metadata: {e}")

        # 4. Export TXT Caption copy
        caption_path = self.output_dir / "instagram_caption.txt"
        sources_str = ", ".join(parsed["source_attribution"]["sources"])
        caption = (
            f"🚀 **KKNova.io Market Brief | Daily Wrap**\n\n"
            f"📊 Mood: {parsed['scorecard']['market_mood']}\n"
            f"🩺 Health Score: {parsed['scorecard']['health_score']}/100 ({parsed['market_health_score']['rating']})\n"
            f"⚡ Smart Money: {parsed['scorecard']['smart_money']}\n"
            f"🛡️ Tomorrow Bias: {parsed['scorecard']['tomorrow_bias']}\n\n"
            f"📝 **Executive Summary**:\n"
            f"_{parsed['scorecard']['one_line_summary']}_\n\n"
            f"💡 **Why Should I Care?**:\n"
            f"• **Long Term**: {parsed['why_should_i_care']['long_term_investors']}\n"
            f"• **Swing Traders**: {parsed['why_should_i_care']['swing_traders']}\n"
            f"• **Beginners**: {parsed['why_should_i_care']['beginners']}\n\n"
            f"📖 **Daily Education**: {parsed['educational_insight']['concept']}\n\n"
            f"📌 **Attribution**: {sources_str}\n\n"
            f"👑 **{parsed['kknova_branding']['signature']}**\n"
            f"\"{parsed['kknova_branding']['quote']}\"\n"
            f"_{parsed['kknova_branding']['disclaimer']}_\n\n"
            f"#KKNova #MarketBrief #Investing #Nifty #IndianStockMarket #Finance"
        )
        try:
            with open(caption_path, "w", encoding="utf-8") as f:
                f.write(caption)
            logger.info(f"Saved Instagram caption text copy: {caption_path}")
            generated_paths.append(caption_path)
        except Exception as e:
            logger.error(f"Failed to write Instagram caption: {e}")

        # 5. Pack everything into a ZIP Archive for Download All Slides ZIP
        zip_path = self.output_dir / "kknova_carousel.zip"
        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_f:
                for path in generated_paths:
                    zip_f.write(path, arcname=path.name)
            logger.info(f"Generated Carousel Complete ZIP Archive: {zip_path}")
            generated_paths.append(zip_path)
        except Exception as e:
            logger.error(f"Failed to package ZIP archive: {e}")

        return generated_paths
