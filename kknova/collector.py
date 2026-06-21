import time
import random
import datetime
import requests
import pandas as pd
import yfinance as yf
from typing import Dict, Any, List, Optional
from kknova.config import config
from kknova.logger import logger
from kknova.database import DatabaseManager

class MarketDataCollector:
    """
    Collects stock index data from Yahoo Finance.
    Handles API retries with exponential backoff and data formatting.
    """
    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db_manager = db_manager

    def fetch_ticker_data_with_retry(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Fetches stock historical data from yfinance with exponential backoff retry logic.
        Includes a fallback to merge monthly history with the latest 1d quote for lagged sectoral indices.
        """
        retries = 0
        max_retries = config.RETRY_COUNT
        backoff_factor = config.RETRY_BACKOFF

        while retries < max_retries:
            try:
                logger.debug(f"Fetching data for {symbol} (Attempt {retries + 1}/{max_retries})...")
                # Instantiate Ticker without custom session
                ticker = yf.Ticker(symbol)
                # Fetch last 5 trading days to ensure we always have 2 valid days of data
                df = ticker.history(period="5d")
                
                if df.empty:
                    raise ValueError(f"No historical data returned for ticker {symbol}")
                
                # Check if we have enough points to compute a daily change (need at least 2 days)
                # Lagged sector indices on weekends often return only 1 day in the 5d window
                if len(df.dropna(subset=["Close"])) < 2:
                    logger.warning(
                        f"Fewer than 2 rows returned for {symbol} in 5d history. "
                        f"Attempting monthly history fallback combined with EOD quote."
                    )
                    df_1mo = ticker.history(period="1mo")
                    df_1d = ticker.history(period="1d")
                    if not df_1mo.empty and not df_1d.empty:
                        # Append latest EOD if it represents a newer date
                        if df_1d.index[-1] > df_1mo.index[-1]:
                            df = pd.concat([df_1mo[~df_1mo.index.isin(df_1d.index)], df_1d])
                        else:
                            df = df_1mo
                    elif not df_1mo.empty:
                        df = df_1mo
                    elif not df_1d.empty:
                        df = df_1d

                return df
            except Exception as e:
                retries += 1
                logger.warning(
                    f"Attempt {retries} failed to fetch {symbol}: {e}. "
                    f"Retrying..."
                )
                if retries >= max_retries:
                    logger.error(f"Failed to fetch {symbol} after {max_retries} attempts.")
                    return None
                
                # Exponential backoff with jitter
                sleep_time = (backoff_factor ** retries) + random.uniform(0.1, 1.0)
                time.sleep(sleep_time)
        return None

    def process_ticker_data(self, name: str, symbol: str, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Extracts and formats current price, previous close, percentage change, and volume.
        """
        try:
            # Clean dataframe: drop rows with missing close price
            df_cleaned = df.dropna(subset=["Close"])
            if len(df_cleaned) < 2:
                logger.error(f"Insufficient historical data for {name} ({symbol}) to calculate daily changes.")
                return None
            
            # Fetch latest and previous day data
            latest_row = df_cleaned.iloc[-1]
            prev_row = df_cleaned.iloc[-2]

            current_price = float(latest_row["Close"])
            previous_close = float(prev_row["Close"])
            
            # Percentage Change
            percentage_change = ((current_price - previous_close) / previous_close) * 100.0
            
            # Handle volume safely (some indices do not report volume)
            volume_val = latest_row.get("Volume", 0)
            volume = int(volume_val) if pd.notna(volume_val) else 0

            # Get current timestamp in ISO 8601 format
            timestamp = datetime.datetime.now().isoformat()

            return {
                "timestamp": timestamp,
                "name": name,
                "symbol": symbol,
                "current_price": round(current_price, 2),
                "previous_close": round(previous_close, 2),
                "percentage_change": round(percentage_change, 2),
                "volume": volume
            }
        except Exception as e:
            logger.error(f"Error parsing dataframe for {name} ({symbol}): {e}")
            return None

    def collect_and_store(self) -> List[Dict[str, Any]]:
        """
        Orchestrates fetching of all configured indices, formats data, 
        and stores it in the respective sqlite3 tables.
        """
        logger.info("Starting market data collection...")
        collected_records: List[Dict[str, Any]] = []

        for name, symbol in config.TICKER_MAPPING.items():
            df = self.fetch_ticker_data_with_retry(symbol)
            if df is None:
                continue

            record = self.process_ticker_data(name, symbol, df)
            if record is None:
                continue

            # Store in Database
            success = False
            if name in config.SECTOR_INDICES:
                success = self.db_manager.insert_sector_data(
                    timestamp=record["timestamp"],
                    symbol=record["symbol"],
                    sector_name=record["name"],
                    current_price=record["current_price"],
                    previous_close=record["previous_close"],
                    percentage_change=record["percentage_change"],
                    volume=record["volume"]
                )
                logger.info(f"Stored Sector Data: {name} | Price: {record['current_price']} | Change: {record['percentage_change']}%")
            else:
                success = self.db_manager.insert_market_data(
                    timestamp=record["timestamp"],
                    symbol=record["symbol"],
                    current_price=record["current_price"],
                    previous_close=record["previous_close"],
                    percentage_change=record["percentage_change"],
                    volume=record["volume"]
                )
                logger.info(f"Stored Market Data: {name} | Price: {record['current_price']} | Change: {record['percentage_change']}%")
            
            if not success:
                logger.error(f"Failed to write record for {name} to SQLite.")
            
            collected_records.append(record)

        logger.info(f"Market data collection completed. Successfully processed {len(collected_records)} indices.")
        return collected_records
