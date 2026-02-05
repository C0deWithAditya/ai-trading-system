"""
Configuration file for the F&O Trading System.
Contains API credentials, trading parameters, and system settings.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class UpstoxConfig:
    """Upstox API configuration."""
    api_key: str = ""
    api_secret: str = ""
    access_token: str = ""
    redirect_uri: str = "http://127.0.0.1:5000/callback"
    
    # API endpoints
    base_url: str = "https://api.upstox.com/v2"
    option_chain_endpoint: str = "/option/chain"
    market_quote_endpoint: str = "/market-quote/quotes"
    historical_candle_endpoint: str = "/historical-candle"
    
    # Instrument keys for NIFTY
    nifty_index_key: str = "NSE_INDEX|Nifty 50"
    nifty_option_key: str = "NSE_FO|NIFTY"


@dataclass
class TelegramConfig:
    """Telegram notification configuration."""
    bot_token: str = ""
    chat_id: str = ""
    enabled: bool = True


@dataclass
class TradingConfig:
    """Trading strategy parameters."""
    # PCR thresholds
    pcr_bullish_threshold: float = 0.7  # PCR below this = bullish
    pcr_bearish_threshold: float = 1.3  # PCR above this = bearish
    
    # OI change thresholds (percentage)
    oi_change_significant: float = 5.0  # 5% change is significant
    
    # VWAP deviation threshold (percentage)
    vwap_deviation_threshold: float = 0.5  # 0.5% deviation from VWAP
    
    # Strike selection
    atm_strike_range: int = 5  # Number of strikes around ATM to consider
    
    # Minimum volume filter
    min_volume: int = 1000
    
    # Minimum OI filter
    min_oi: int = 10000


@dataclass
class SystemConfig:
    """System settings."""
    refresh_interval_seconds: int = 60
    log_level: str = "INFO"
    log_file: str = "trading_system.log"
    data_snapshot_dir: str = "snapshots"


@dataclass
class AIConfig:
    """AI/Gemini configuration."""
    api_key: str = ""
    enabled: bool = True
    min_confidence: int = 55  # Minimum confidence to send alert
    model: str = "gemini-1.5-flash"


# Load configuration from environment variables or use defaults
def load_config():
    """Load configuration from environment variables."""
    upstox = UpstoxConfig(
        api_key=os.getenv("UPSTOX_API_KEY", ""),
        api_secret=os.getenv("UPSTOX_API_SECRET", ""),
        access_token=os.getenv("UPSTOX_ACCESS_TOKEN", ""),
    )
    
    telegram = TelegramConfig(
        bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        enabled=os.getenv("TELEGRAM_ENABLED", "true").lower() == "true",
    )
    
    ai = AIConfig(
        api_key=os.getenv("GEMINI_API_KEY", ""),
        enabled=os.getenv("AI_ENABLED", "true").lower() == "true",
        min_confidence=int(os.getenv("AI_MIN_CONFIDENCE", "50")),
    )
    
    trading = TradingConfig()
    system = SystemConfig()
    
    return upstox, telegram, trading, system, ai


# Global config instances
UPSTOX_CONFIG, TELEGRAM_CONFIG, TRADING_CONFIG, SYSTEM_CONFIG, AI_CONFIG = load_config()

