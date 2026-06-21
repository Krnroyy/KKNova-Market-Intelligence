import datetime
from typing import Dict, Any, List, Tuple
from kknova.config import config
from kknova.logger import logger
from kknova.database import DatabaseManager
from kknova.ai_analyst import AIAnalyst
from kknova.telegram_sender import TelegramSender

class ReportGenerator:
    """
    Orchestrates the retrieval of market stats, rankings, and news;
    invokes the AI Analyst to compile a structured V4.1 JSON brief;
    saves the brief in the DB; and triggers the Telegram Sender.
    """
    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db_manager = db_manager
        self.analyst = AIAnalyst()
        self.telegram = TelegramSender()

    def generate_and_send_report(self, report_type: str) -> str:
        """
        Retrieves recent metrics, triggers Gemini/Fallback JSON analysis,
        saves the report to the reports table, and broadcasts it to Telegram.
        """
        logger.info(f"Initiating generation of {report_type.upper()} report brief...")
        timestamp = datetime.datetime.now().isoformat()
        
        # 1. Fetch raw datasets from database under active connection
        with self.db_manager as db:
            # Get latest indices quotes
            symbols = list(config.TICKER_MAPPING.values())
            market_data = []
            for symbol in symbols:
                if symbol == "^NSEI" or symbol == "^NSEBANK":
                    quote = db.get_latest_market_data_for_symbol(symbol)
                else:
                    quote = db.get_latest_sector_data_for_symbol(symbol)
                if quote:
                    market_data.append(quote)

            # Get latest sector rankings (limit 15)
            sql = "SELECT sector_name, score FROM sector_rankings ORDER BY timestamp DESC, rank ASC LIMIT 15"
            cursor = db._execute(sql)
            sector_rankings = []
            if cursor:
                # Deduplicate rankings inside query load
                seen_sec = set()
                for row in cursor.fetchall():
                    sec_name = row["sector_name"]
                    if sec_name not in seen_sec:
                        seen_sec.add(sec_name)
                        sector_rankings.append((sec_name, row["score"]))

            # Get latest news headlines (limit 15)
            sql = "SELECT category, title, source FROM news_data ORDER BY timestamp DESC, publish_date DESC LIMIT 15"
            cursor = db._execute(sql)
            news_articles = []
            if cursor:
                news_articles = [dict(row) for row in cursor.fetchall()]

        # Calculate scraping success rate based on symbols count
        total_symbols = len(symbols) if symbols else 1
        scraping_success_rate = len(market_data) / total_symbols

        # Error Resilience Fallback System: if market_data is empty, use cached data
        if not market_data:
            logger.warning("No fresh market data available in DB. Falling back to rule-based mock engine.")
            scraping_success_rate = 0.0

        # 2. Trigger analysis (Gemini returns a validated JSON string)
        report_content = self.analyst.analyze_market(
            market_data=market_data,
            sector_rankings=sector_rankings,
            news_articles=news_articles,
            scraping_success_rate=scraping_success_rate
        )

        if not report_content:
            logger.error("Report content generation returned empty result.")
            return ""

        # 3. Save report to SQLite reports table
        with self.db_manager as db:
            success = db.insert_report(
                timestamp=timestamp,
                report_type=report_type.upper(),
                content=report_content,
                status="COMPLETED"
            )
            if success:
                logger.info(f"Saved {report_type.upper()} report JSON brief to database reports archive.")
            else:
                logger.error("Failed to archive report brief to database.")

        # 4. Publish report to Telegram (falls back to local files if token missing)
        self.telegram.send_report(report_content)
        
        return report_content
