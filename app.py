import argparse
import sys
import time
import schedule
from kknova.config import config
from kknova.logger import logger
from kknova.database import DatabaseManager
from kknova.collector import MarketDataCollector
from kknova.news_collector import NewsCollector
from kknova.sector_strength_engine import SectorStrengthEngine
from kknova.report_generator import ReportGenerator

def run_pipeline(db_manager: DatabaseManager, report_type: str) -> None:
    """
    Orchestrates the complete data scraping, ranking calculation,
    and report generation/telegram dispatch flow.
    """
    logger.info(f"====================================================")
    logger.info(f"STARTING PIPELINE: {report_type.upper()} REPORT")
    logger.info(f"====================================================")
    try:
        # Step 1: Initialize Database tables
        with db_manager as db:
            db.initialize_database()

        # Step 2: Fetch market prices
        collector = MarketDataCollector(db_manager)
        with db_manager as db:
            collector.collect_and_store()

        # Step 3: Fetch news articles
        news_collector = NewsCollector(db_manager)
        with db_manager as db:
            news_collector.collect_and_store_news()

        # Step 4: Run strength engine calculations
        strength_engine = SectorStrengthEngine(db_manager)
        with db_manager as db:
            strength_engine.run_engine()

        # Step 5: Generate AI Analyst report and send via Telegram
        report_gen = ReportGenerator(db_manager)
        report_content = report_gen.generate_and_send_report(report_type)

        # Step 6: Generate Instagram Carousel package
        if report_content:
            from kknova.carousel_generator import InstagramCarouselGenerator
            logger.info("Auto-building Instagram Carousel slides...")
            carousel_gen = InstagramCarouselGenerator()
            carousel_gen.generate_carousel_package(report_content)

        logger.info(f"====================================================")
        logger.info(f"PIPELINE COMPLETED: {report_type.upper()} REPORT SUCCESSFUL")
        logger.info(f"====================================================")

    except Exception as e:
        logger.error(f"Pipeline failed for {report_type} report: {e}", exc_info=True)


def main() -> None:
    """
    Main runner script supporting one-off execution, report triggers,
    and background scheduling daemon.
    """
    parser = argparse.ArgumentParser(description="KKNova Market Intelligence Engine")
    parser.add_argument(
        "--report",
        choices=["morning", "closing"],
        help="Execute and dispatch a one-off report (morning or closing) immediately."
    )
    parser.add_argument(
        "--scheduler",
        action="store_true",
        help="Run in background daemon mode (8:00 AM and 4:00 PM executions)."
    )
    
    args = parser.parse_args()
    db_manager = DatabaseManager(config.db_absolute_path)

    # 1. Daemon Scheduler Mode
    if args.scheduler:
        logger.info("Initializing 24/7 background scheduler daemon mode...")
        # Schedule morning report daily at 8:00 AM
        schedule.every().day.at("08:00").do(run_pipeline, db_manager=db_manager, report_type="morning")
        # Schedule closing report daily at 4:00 PM (16:00)
        schedule.every().day.at("16:00").do(run_pipeline, db_manager=db_manager, report_type="closing")
        
        logger.info("Tasks scheduled successfully. Running daemon loop (Ctrl+C to exit)...")
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Scheduler daemon shut down gracefully.")
            sys.exit(0)

    # 2. One-Off Specific Report Trigger Mode
    elif args.report:
        run_pipeline(db_manager, args.report)

    # 3. Standard EOD Calculations Pipeline (Phase 2 default behavior)
    else:
        logger.info("Running default EOD market and sector analysis (No Telegram report dispatch)...")
        try:
            with db_manager as db:
                db.initialize_database()
            
            collector = MarketDataCollector(db_manager)
            with db_manager as db:
                collector.collect_and_store()

            news_collector = NewsCollector(db_manager)
            with db_manager as db:
                news_collector.collect_and_store_news()

            strength_engine = SectorStrengthEngine(db_manager)
            with db_manager as db:
                rankings = strength_engine.run_engine()

            if rankings:
                logger.info("\n>>> Top Strongest Sectors (Ranked 1 to 5):")
                print(f"{'Rank':<5} | {'Sector Name':<20} | {'Score':<8}")
                print("-" * 40)
                for idx, (sector, score) in enumerate(rankings[:5], start=1):
                    print(f"{idx:<5} | {sector:<20} | {score:<8.2f}")
                print("-" * 40)
            else:
                logger.warning("No rankings could be generated.")
        except Exception as e:
            logger.critical(f"EOD execution failed: {e}", exc_info=True)
            sys.exit(1)


if __name__ == "__main__":
    main()
