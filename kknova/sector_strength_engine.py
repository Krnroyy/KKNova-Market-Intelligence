import datetime
from typing import Dict, Any, List, Tuple, Optional
from kknova.config import config
from kknova.logger import logger
from kknova.database import DatabaseManager

class SectorStrengthEngine:
    """
    Computes daily strength scores for sectors based on market performance,
    relative strength against Nifty 50, trade volume change, and news density.
    Saves daily rankings and outputs strongest/weakest lists.
    """
    
    # Map index names to news category classifications
    SECTOR_CATEGORY_MAP = {
        "Bank Nifty": "Banking",
        "Finnifty": "Finance",
        "Nifty IT": "IT",
        "Nifty Auto": "Auto",
        "Nifty Pharma": "Pharma",
        "Nifty FMCG": "FMCG",
        "Nifty Realty": "Realty",
        "Nifty Metal": "Metal",
        "Nifty Energy": "Energy",
        "Nifty PSU Bank": "PSU",
        "Nifty Infra": "Infrastructure"
    }

    # Map sector names to their yfinance symbols in DB
    SECTOR_SYMBOL_MAP = {
        "Bank Nifty": "^NSEBANK",
        "Finnifty": "^CNXFIN",
        "Nifty IT": "^CNXIT",
        "Nifty Auto": "^CNXAUTO",
        "Nifty Pharma": "^CNXPHARMA",
        "Nifty FMCG": "^CNXFMCG",
        "Nifty Realty": "^CNXREALTY",
        "Nifty Metal": "^CNXMETAL",
        "Nifty Energy": "^CNXENERGY",
        "Nifty PSU Bank": "^CNXPSUBANK",
        "Nifty Infra": "^CNXINFRA"
    }

    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db_manager = db_manager

    def _normalize_list(self, values: List[float]) -> List[float]:
        """Normalizes a list of values to a 0-100 scale using min-max normalization."""
        if not values:
            return []
        v_min = min(values)
        v_max = max(values)
        
        if v_max == v_min:
            return [50.0] * len(values)
            
        return [100.0 * (v - v_min) / (v_max - v_min) for v in values]

    def fetch_raw_metrics(self) -> Dict[str, Dict[str, float]]:
        """
        Retrieves raw performance, relative strength, volume ratio, and news counts
        for all sectors from the SQLite database.
        """
        now = datetime.datetime.now()
        since_24h = (now - datetime.timedelta(hours=24)).isoformat()

        # 1. Fetch Nifty 50 benchmark
        nifty_quote = self.db_manager.get_latest_market_data_for_symbol("^NSEI")
        nifty_change = nifty_quote["percentage_change"] if nifty_quote else 0.0
        logger.debug(f"Benchmarking against Nifty 50 daily change: {nifty_change}%")

        raw_data = {}

        for sector_name, symbol in self.SECTOR_SYMBOL_MAP.items():
            # 2. Get latest EOD price quote (check sector_data, fallback to market_data)
            quote = self.db_manager.get_latest_sector_data_for_symbol(symbol)
            if not quote:
                quote = self.db_manager.get_latest_market_data_for_symbol(symbol)

            if not quote:
                logger.warning(f"No recent market quote found in DB for {sector_name} ({symbol}). Skipping score.")
                continue

            price_change = quote["percentage_change"]
            current_volume = quote["volume"]

            # 3. Calculate volume ratio (current / historical avg)
            volumes = self.db_manager.get_historical_sector_volumes(symbol, limit=5)
            # Filter out current run volume if it is at index 0
            if len(volumes) >= 2:
                prev_volume = volumes[1]
                volume_ratio = current_volume / prev_volume if prev_volume > 0 else 1.0
            else:
                volume_ratio = 1.0

            # 4. Calculate relative strength
            relative_strength = price_change - nifty_change

            # 5. Fetch News Category Density in last 24h
            news_category = self.SECTOR_CATEGORY_MAP.get(sector_name, "General")
            news_count = self.db_manager.get_news_count_by_category(news_category, since_24h)

            raw_data[sector_name] = {
                "price_performance": price_change,
                "volume_strength": volume_ratio,
                "relative_strength": relative_strength,
                "news_activity": float(news_count)
            }

            logger.debug(
                f"Raw Metrics - {sector_name}: Price Change={price_change}%, "
                f"Vol Ratio={volume_ratio:.2f}, Rel Strength={relative_strength:+.2f}%, News Count={news_count}"
            )

        return raw_data

    def calculate_scores(self, raw_data: Dict[str, Dict[str, float]]) -> List[Tuple[str, float]]:
        """
        Normalizes individual metrics and computes the weighted Sector Strength Score.
        Returns a sorted list of (sector_name, final_score) tuples (descending).
        """
        if not raw_data:
            return []

        sectors = list(raw_data.keys())
        
        # Extract lists for normalization
        price_vals = [raw_data[s]["price_performance"] for s in sectors]
        volume_vals = [raw_data[s]["volume_strength"] for s in sectors]
        rel_vals = [raw_data[s]["relative_strength"] for s in sectors]
        news_vals = [raw_data[s]["news_activity"] for s in sectors]

        # Normalize metrics
        norm_price = self._normalize_list(price_vals)
        norm_volume = self._normalize_list(volume_vals)
        norm_rel = self._normalize_list(rel_vals)
        norm_news = self._normalize_list(news_vals)

        scores = []
        for idx, sector in enumerate(sectors):
            # Apply weights: 40% Price, 20% Volume, 20% Relative Strength, 20% News Density
            final_score = (
                0.40 * norm_price[idx] +
                0.20 * norm_volume[idx] +
                0.20 * norm_rel[idx] +
                0.20 * norm_news[idx]
            )
            scores.append((sector, round(final_score, 2)))

        # Sort descending by score
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

    def run_engine(self) -> List[Tuple[str, float]]:
        """
        Runs the Sector Strength Engine pipeline:
        Fetches metrics, computes rankings, saves daily ranks, and returns rankings.
        """
        logger.info("Executing Sector Strength calculation...")
        raw_data = self.fetch_raw_metrics()
        
        if not raw_data:
            logger.error("No sectoral metrics could be fetched. Strength Engine aborted.")
            return []

        ranked_sectors = self.calculate_scores(raw_data)
        
        if not ranked_sectors:
            return []

        # Store rankings in Database
        timestamp = datetime.datetime.now().isoformat()
        with self.db_manager as db:
            for rank, (sector, score) in enumerate(ranked_sectors, start=1):
                db.insert_sector_ranking(
                    timestamp=timestamp,
                    sector_name=sector,
                    score=score,
                    rank=rank
                )
        
        logger.info(f"Sector Strength calculation complete. Saved {len(ranked_sectors)} sector rankings.")
        return ranked_sectors
