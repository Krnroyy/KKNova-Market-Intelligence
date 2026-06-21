import logging
import sqlite3
import datetime
from pathlib import Path
from kknova.config import config

class SQLiteLogHandler(logging.Handler):
    """
    Custom logging handler that writes log records to the SQLite logs table.
    Ensures safe database writes and prevents recursive logging errors.
    """
    def __init__(self, db_path: Path):
        super().__init__()
        self.db_path = db_path

    def emit(self, record: logging.LogRecord) -> None:
        # Avoid database logging for database-related operations to prevent infinite loops
        if record.name == "kknova.database":
            return
            
        conn = None
        try:
            log_message = self.format(record)
            timestamp = datetime.datetime.now().isoformat()
            
            # Use direct sqlite3 connection here to avoid dependency loops
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO logs (timestamp, level, message, module) VALUES (?, ?, ?, ?)",
                (timestamp, record.levelname, log_message, record.module)
            )
            conn.commit()
        except Exception:
            # Silent fallback to prevent logging failure from crashing the app
            pass
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass


def setup_logger(name: str = "kknova") -> logging.Logger:
    """
    Configures and returns the application logger.
    Logs to stdout, local file, and SQLite logs table.
    """
    logger = logging.getLogger(name)
    logger.setLevel(config.LOG_LEVEL)

    # Prevent duplicate handlers if logger is already configured
    if logger.handlers:
        return logger

    # Log Formatter
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] [%(module)s]: %(message)s"
    )

    # 1. Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(config.LOG_LEVEL)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 2. File Handler
    try:
        log_file_path = config.log_absolute_path
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
        file_handler.setLevel(config.LOG_LEVEL)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.error(f"Failed to initialize file logger: {e}")

    # 3. Database Handler
    try:
        db_handler = SQLiteLogHandler(config.db_absolute_path)
        db_handler.setLevel(logging.WARNING)  # Log WARNING and higher to SQLite logs table to save space
        db_handler.setFormatter(formatter)
        logger.addHandler(db_handler)
    except Exception as e:
        logger.error(f"Failed to initialize SQLite log handler: {e}")

    return logger

# Initialize global logger
logger = setup_logger()
