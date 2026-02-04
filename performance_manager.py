import sqlite3
import json
import logging
from datetime import datetime
import pytz
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class MarketPerformanceManager:
    """Manages long-term storage of trades and EOD analysis for self-improvement."""
    
    def __init__(self, db_path: str = "trading_history.db"):
        self.db_path = db_path
        self._init_db()
        self.ist = pytz.timezone('Asia/Kolkata')
        
    def _init_db(self):
        """Initialize SQLite database for historical records."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Table for individual trades
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id INTEGER,
                    symbol TEXT,
                    signal_type TEXT,
                    strike INTEGER,
                    entry_price REAL,
                    exit_price REAL,
                    pnl REAL,
                    roi REAL,
                    entry_time TEXT,
                    exit_time TEXT,
                    status TEXT,
                    reasoning TEXT,
                    market_context TEXT
                )
            ''')
            
            # Table for daily analysis/memory
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_analysis (
                    date TEXT PRIMARY KEY,
                    total_trades INTEGER,
                    win_rate REAL,
                    total_pnl REAL,
                    key_learnings TEXT,
                    market_summary TEXT
                )
            ''')
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error initializing database: {e}")

    def log_trade(self, trade_dict: Dict[str, Any]):
        """Save a finalized trade to the database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO trades (
                    trade_id, symbol, signal_type, strike, entry_price, 
                    exit_price, pnl, roi, entry_time, exit_time, 
                    status, reasoning, market_context
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trade_dict.get('id'),
                trade_dict.get('index'),
                trade_dict.get('signal_type'),
                trade_dict.get('strike'),
                trade_dict.get('entry_premium'),
                trade_dict.get('exit_premium'),
                trade_dict.get('pnl'),
                trade_dict.get('roi_percentage'),
                trade_dict.get('entry_time'),
                trade_dict.get('exit_time'),
                trade_dict.get('status'),
                trade_dict.get('reasoning', ''),
                json.dumps(trade_dict.get('market_context', {}))
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"✅ Trade {trade_dict.get('id')} logged to permanent database.")
        except Exception as e:
            logger.error(f"Error logging trade to DB: {e}")

    def get_daily_trades(self, trade_date: str) -> List[Dict]:
        """Fetch all trades for a specific date (YYYY-MM-DD)."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Match date prefix in entry_time
            cursor.execute("SELECT * FROM trades WHERE entry_time LIKE ?", (f"{trade_date}%",))
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error fetching daily trades: {e}")
            return []

    def save_daily_analysis(self, date_str: str, analysis: Dict[str, Any]):
        """Save the EOD analysis and learnings."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO daily_analysis (
                    date, total_trades, win_rate, total_pnl, key_learnings, market_summary
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                date_str,
                analysis.get('total_trades', 0),
                analysis.get('win_rate', 0.0),
                analysis.get('total_pnl', 0.0),
                analysis.get('key_learnings', ''),
                analysis.get('market_summary', '')
            ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error saving daily analysis: {e}")

    def get_recent_learnings(self, limit: int = 5) -> str:
        """Get the most recent trading lessons for AI context."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT key_learnings FROM daily_analysis ORDER BY date DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                return "No previous learnings found. Initializing trading strategy."
            
            learnings = "\n".join([f"- {row[0]}" for row in rows if row[0]])
            return learnings
        except Exception as e:
            logger.error(f"Error fetching learnings: {e}")
            return ""

_perm_manager = None

def get_performance_manager():
    global _perm_manager
    if _perm_manager is None:
        _perm_manager = MarketPerformanceManager()
    return _perm_manager
