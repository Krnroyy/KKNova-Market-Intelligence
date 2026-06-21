import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """
    Configuration manager for KKNova Market Intelligence Engine.
    Loads and validates settings from environment variables.
    """
    # Project Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    
    # Database Settings
    DB_PATH: str = os.getenv("DB_PATH", "kknova.db")
    NEWS_API_KEY: str = os.getenv("NEWS_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    
    @property
    def db_absolute_path(self) -> Path:
        """Returns the absolute path to the SQLite database."""
        path = Path(self.DB_PATH)
        if not path.is_absolute():
            return self.BASE_DIR / path
        return path

    # Logging Settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_FILE: str = os.getenv("LOG_FILE", "kknova.log")

    @property
    def log_absolute_path(self) -> Path:
        """Returns the absolute path to the log file."""
        path = Path(self.LOG_FILE)
        if not path.is_absolute():
            return self.BASE_DIR / path
        return path

    # Market Data Collection Settings
    RETRY_COUNT: int = int(os.getenv("RETRY_COUNT", "3"))
    RETRY_BACKOFF: float = float(os.getenv("RETRY_BACKOFF", "2.0"))

    # Ticker Mappings (Yahoo Finance symbols for Indian market indices/sectors)
    TICKER_MAPPING: dict[str, str] = {
        # Broad Indices
        "Nifty 50": "^NSEI",
        "Bank Nifty": "^NSEBANK",
        "Finnifty": "^CNXFIN",
        "Nifty Midcap 100": "^CRSMID",
        "Nifty Smallcap 100": "^CNXSC",
        # Sectors
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

    # Sectors list for categorizing data insertions
    SECTOR_INDICES: set[str] = {
        "Bank Nifty",
        "Finnifty",
        "Nifty IT",
        "Nifty Auto",
        "Nifty Pharma",
        "Nifty FMCG",
        "Nifty Realty",
        "Nifty Metal",
        "Nifty Energy",
        "Nifty PSU Bank",
        "Nifty Infra"
    }

    # Top constituents for each sector
    SECTOR_CONSTITUENTS: dict[str, list[str]] = {
        "Bank Nifty": ["HDFC Bank", "ICICI Bank", "SBI", "Kotak Bank", "Axis Bank"],
        "Finnifty": ["HDFC Bank", "ICICI Bank", "Bajaj Finance", "SBI", "HDFC Life"],
        "Nifty IT": ["TCS", "Infosys", "Wipro", "HCL Tech", "Tech Mahindra"],
        "Nifty Auto": ["Maruti Suzuki", "M&M", "Tata Motors", "Bajaj Auto", "Eicher Motors"],
        "Nifty Pharma": ["Sun Pharma", "Cipla", "Dr. Reddy's", "Divi's Lab", "Lupin"],
        "Nifty FMCG": ["Hindustan Unilever", "ITC", "Nestle India", "Britannia", "Tata Consumer"],
        "Nifty Realty": ["DLF", "Macrotech Developers", "Godrej Properties", "Phoenix Mills", "Oberoi Realty"],
        "Nifty Metal": ["Tata Steel", "JSW Steel", "Hindalco", "Coal India", "Jindal Steel"],
        "Nifty Energy": ["Reliance Industries", "NTPC", "ONGC", "Power Grid", "BPCL"],
        "Nifty PSU Bank": ["SBI", "Bank of Baroda", "PNB", "Canara Bank", "Union Bank"],
        "Nifty Infra": ["L&T", "Reliance Industries", "NTPC", "Bharti Airtel", "Adani Ports"]
    }


# Create a global config instance
config = Config()
