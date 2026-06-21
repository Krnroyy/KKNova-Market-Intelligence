import sqlite3
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Obtain a dedicated logger for the database module
db_logger = logging.getLogger("kknova.database")

class DatabaseManager:
    """
    Manages SQLite database connections, schema creation, data insertion, and queries.
    Implements the Context Manager pattern for safe transactional control.
    """
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._entry_count = 0

    def __enter__(self) -> "DatabaseManager":
        if self._entry_count == 0:
            try:
                self._conn = sqlite3.connect(self.db_path, timeout=10.0)
                self._conn.row_factory = sqlite3.Row
                # Enable Foreign Key constraints
                self._conn.execute("PRAGMA foreign_keys = ON;")
            except sqlite3.Error as e:
                db_logger.error(f"Failed to connect to SQLite database at {self.db_path}: {e}")
                raise
        self._entry_count += 1
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._entry_count -= 1
        if self._entry_count == 0:
            if self._conn:
                try:
                    if exc_type:
                        self._conn.rollback()
                        db_logger.warning(f"Transaction rolled back due to error: {exc_val}")
                    else:
                        self._conn.commit()
                except sqlite3.Error as e:
                    db_logger.error(f"Error during transaction commit/rollback: {e}")
                finally:
                    self._conn.close()
                    self._conn = None

    def _execute(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Cursor]:
        """Helper method to execute SQL query inside transaction."""
        if not self._conn:
            raise RuntimeError("Database connection is not open. Use context manager 'with'.")
        try:
            return self._conn.execute(sql, params)
        except sqlite3.Error as e:
            db_logger.error(f"Database error executing SQL: {sql} | Params: {params} | Error: {e}")
            raise

    def initialize_database(self) -> None:
        """Initializes tables (market_data, sector_data, reports, logs) if they do not exist."""
        db_logger.info("Initializing SQLite database tables...")
        
        # 1. market_data table
        self._execute(
            """
            CREATE TABLE IF NOT EXISTS market_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                current_price REAL NOT NULL,
                previous_close REAL NOT NULL,
                percentage_change REAL NOT NULL,
                volume INTEGER NOT NULL,
                UNIQUE(timestamp, symbol)
            );
            """
        )

        # 2. sector_data table
        self._execute(
            """
            CREATE TABLE IF NOT EXISTS sector_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                sector_name TEXT NOT NULL,
                current_price REAL NOT NULL,
                previous_close REAL NOT NULL,
                percentage_change REAL NOT NULL,
                volume INTEGER NOT NULL,
                UNIQUE(timestamp, symbol)
            );
            """
        )

        # 3. reports table
        self._execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                report_type TEXT NOT NULL,
                content TEXT NOT NULL,
                status TEXT NOT NULL
            );
            """
        )

        # 4. logs table
        self._execute(
            """
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                module TEXT NOT NULL
            );
            """
        )
        
        # 5. news_data table
        self._execute(
            """
            CREATE TABLE IF NOT EXISTS news_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                title TEXT NOT NULL,
                source TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                publish_date TEXT NOT NULL,
                category TEXT NOT NULL
            );
            """
        )

        # 6. sector_rankings table
        self._execute(
            """
            CREATE TABLE IF NOT EXISTS sector_rankings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                sector_name TEXT NOT NULL,
                score REAL NOT NULL,
                rank INTEGER NOT NULL,
                UNIQUE(timestamp, sector_name)
            );
            """
        )

        # 7. portfolio_holdings table
        self._execute(
            """
            CREATE TABLE IF NOT EXISTS portfolio_holdings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL UNIQUE,
                shares REAL NOT NULL,
                buy_price REAL NOT NULL,
                sector TEXT NOT NULL
            );
            """
        )

        # 8. watchlists table
        self._execute(
            """
            CREATE TABLE IF NOT EXISTS watchlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                name TEXT NOT NULL,
                symbol TEXT NOT NULL,
                UNIQUE(name, symbol)
            );
            """
        )
        
        # Create indexes to speed up searches
        self._execute("CREATE INDEX IF NOT EXISTS idx_market_data_symbol ON market_data(symbol);")
        self._execute("CREATE INDEX IF NOT EXISTS idx_sector_data_symbol ON sector_data(symbol);")
        self._execute("CREATE INDEX IF NOT EXISTS idx_news_data_category ON news_data(category);")
        self._execute("CREATE INDEX IF NOT EXISTS idx_sector_rankings_sector ON sector_rankings(sector_name);")
        self._execute("CREATE INDEX IF NOT EXISTS idx_portfolio_holdings_symbol ON portfolio_holdings(symbol);")
        self._execute("CREATE INDEX IF NOT EXISTS idx_watchlists_name ON watchlists(name);")
        
        db_logger.info("Database tables initialized successfully.")

    def insert_market_data(
        self,
        timestamp: str,
        symbol: str,
        current_price: float,
        previous_close: float,
        percentage_change: float,
        volume: int
    ) -> bool:
        """Inserts or replaces market data record."""
        sql = """
            INSERT OR REPLACE INTO market_data 
            (timestamp, symbol, current_price, previous_close, percentage_change, volume) 
            VALUES (?, ?, ?, ?, ?, ?)
        """
        try:
            self._execute(sql, (timestamp, symbol, current_price, previous_close, percentage_change, volume))
            return True
        except sqlite3.Error:
            return False

    def insert_sector_data(
        self,
        timestamp: str,
        symbol: str,
        sector_name: str,
        current_price: float,
        previous_close: float,
        percentage_change: float,
        volume: int
    ) -> bool:
        """Inserts or replaces sector data record."""
        sql = """
            INSERT OR REPLACE INTO sector_data 
            (timestamp, symbol, sector_name, current_price, previous_close, percentage_change, volume) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        try:
            self._execute(
                sql,
                (timestamp, symbol, sector_name, current_price, previous_close, percentage_change, volume)
            )
            return True
        except sqlite3.Error:
            return False

    def insert_report(self, timestamp: str, report_type: str, content: str, status: str) -> bool:
        """Inserts a new report record."""
        sql = "INSERT INTO reports (timestamp, report_type, content, status) VALUES (?, ?, ?, ?)"
        try:
            self._execute(sql, (timestamp, report_type, content, status))
            return True
        except sqlite3.Error:
            return False

    def get_latest_market_data(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves latest records from the market_data table."""
        sql = "SELECT * FROM market_data ORDER BY timestamp DESC, symbol ASC LIMIT ?"
        cursor = self._execute(sql, (limit,))
        if cursor:
            return [dict(row) for row in cursor.fetchall()]
        return []

    def get_latest_sector_data(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves latest records from the sector_data table."""
        sql = "SELECT * FROM sector_data ORDER BY timestamp DESC, symbol ASC LIMIT ?"
        cursor = self._execute(sql, (limit,))
        if cursor:
            return [dict(row) for row in cursor.fetchall()]
        return []

    def insert_news_article(
        self,
        timestamp: str,
        title: str,
        source: str,
        url: str,
        publish_date: str,
        category: str
    ) -> bool:
        """Inserts a new article. Ignores duplicate URLs automatically."""
        sql = """
            INSERT OR IGNORE INTO news_data 
            (timestamp, title, source, url, publish_date, category) 
            VALUES (?, ?, ?, ?, ?, ?)
        """
        try:
            self._execute(sql, (timestamp, title, source, url, publish_date, category))
            return True
        except sqlite3.Error:
            return False

    def insert_sector_ranking(
        self,
        timestamp: str,
        sector_name: str,
        score: float,
        rank: int
    ) -> bool:
        """Inserts or replaces a sector ranking record."""
        sql = """
            INSERT OR REPLACE INTO sector_rankings 
            (timestamp, sector_name, score, rank) 
            VALUES (?, ?, ?, ?)
        """
        try:
            self._execute(sql, (timestamp, sector_name, score, rank))
            return True
        except sqlite3.Error:
            return False

    def get_news_count_by_category(self, category: str, since_timestamp: str) -> int:
        """Counts news articles classified in a category since a given ISO-8601 timestamp."""
        sql = "SELECT COUNT(*) FROM news_data WHERE category = ? AND timestamp >= ?"
        cursor = self._execute(sql, (category, since_timestamp))
        if cursor:
            row = cursor.fetchone()
            return row[0] if row else 0
        return 0

    def get_historical_sector_volumes(self, symbol: str, limit: int = 5) -> List[int]:
        """Retrieves historical trade volumes for a sector symbol, ordered by latest date."""
        sql = "SELECT volume FROM sector_data WHERE symbol = ? ORDER BY timestamp DESC LIMIT ?"
        cursor = self._execute(sql, (symbol, limit))
        if cursor:
            return [row["volume"] for row in cursor.fetchall()]
        return []

    def get_latest_market_data_for_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Retrieves latest quote for a broad index symbol."""
        sql = "SELECT * FROM market_data WHERE symbol = ? ORDER BY timestamp DESC LIMIT 1"
        cursor = self._execute(sql, (symbol,))
        if cursor:
            row = cursor.fetchone()
            return dict(row) if row else None
        return None

    def get_latest_sector_data_for_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Retrieves latest quote for a sector index symbol."""
        sql = "SELECT * FROM sector_data WHERE symbol = ? ORDER BY timestamp DESC LIMIT 1"
        cursor = self._execute(sql, (symbol,))
        if cursor:
            row = cursor.fetchone()
            return dict(row) if row else None
        return None

    # --- PORTFOLIO & WATCHLIST CRUD METHODS ---

    def insert_portfolio_holding(
        self,
        timestamp: str,
        symbol: str,
        shares: float,
        buy_price: float,
        sector: str
    ) -> bool:
        """Inserts or replaces a portfolio holding."""
        sql = """
            INSERT OR REPLACE INTO portfolio_holdings 
            (timestamp, symbol, shares, buy_price, sector) 
            VALUES (?, ?, ?, ?, ?)
        """
        try:
            self._execute(sql, (timestamp, symbol.upper(), shares, buy_price, sector))
            return True
        except sqlite3.Error:
            return False

    def delete_portfolio_holding(self, symbol: str) -> bool:
        """Deletes a portfolio holding by symbol."""
        sql = "DELETE FROM portfolio_holdings WHERE symbol = ?"
        try:
            self._execute(sql, (symbol.upper(),))
            return True
        except sqlite3.Error:
            return False

    def get_portfolio_holdings(self) -> List[Dict[str, Any]]:
        """Retrieves all portfolio holdings."""
        sql = "SELECT * FROM portfolio_holdings ORDER BY symbol ASC"
        cursor = self._execute(sql)
        if cursor:
            return [dict(row) for row in cursor.fetchall()]
        return []

    def get_watchlist_names(self) -> List[str]:
        """Retrieves all unique watchlist names."""
        sql = "SELECT DISTINCT name FROM watchlists ORDER BY name ASC"
        cursor = self._execute(sql)
        if cursor:
            return [row["name"] for row in cursor.fetchall()]
        return []

    def get_watchlist_items(self, name: str) -> List[Dict[str, Any]]:
        """Retrieves all items for a given watchlist name."""
        sql = "SELECT * FROM watchlists WHERE name = ? ORDER BY symbol ASC"
        cursor = self._execute(sql, (name,))
        if cursor:
            return [dict(row) for row in cursor.fetchall()]
        return []

    def insert_watchlist_item(self, timestamp: str, name: str, symbol: str) -> bool:
        """Inserts a new watchlist item. Ignores duplicates."""
        sql = """
            INSERT OR IGNORE INTO watchlists 
            (timestamp, name, symbol) 
            VALUES (?, ?, ?)
        """
        try:
            self._execute(sql, (timestamp, name.strip(), symbol.upper().strip()))
            return True
        except sqlite3.Error:
            return False

    def delete_watchlist_item(self, name: str, symbol: str) -> bool:
        """Deletes a watchlist item."""
        sql = "DELETE FROM watchlists WHERE name = ? AND symbol = ?"
        try:
            self._execute(sql, (name, symbol.upper()))
            return True
        except sqlite3.Error:
            return False

    def delete_watchlist(self, name: str) -> bool:
        """Deletes an entire watchlist."""
        sql = "DELETE FROM watchlists WHERE name = ?"
        try:
            self._execute(sql, (name,))
            return True
        except sqlite3.Error:
            return False

