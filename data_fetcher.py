"""
Data Fetcher Module for the F&O Trading System.
Fetches NIFTY option chain, price, and candle data from Upstox API.

API Response Structures (from official Upstox documentation):

1. Option Chain Response (/v2/option/chain):
{
    "status": "success",
    "data": [
        {
            "expiry": "2025-02-13",
            "pcr": 7515.3,
            "strike_price": 21100,
            "underlying_key": "NSE_INDEX|Nifty 50",
            "underlying_spot_price": 22976.2,
            "call_options": {
                "instrument_key": "NSE_FO|51059",
                "market_data": {
                    "ltp": 2449.9,
                    "volume": 0,
                    "oi": 750,
                    "close_price": 2449.9,
                    "bid_price": 1856.65,
                    "bid_qty": 1125,
                    "ask_price": 1941.65,
                    "ask_qty": 1125,
                    "prev_oi": 1500
                },
                "option_greeks": {
                    "vega": 4.1731,
                    "theta": -472.8941,
                    "gamma": 0.0001,
                    "delta": 0.743,
                    "iv": 262.31,
                    "pop": 40.56
                }
            },
            "put_options": {
                "instrument_key": "NSE_FO|51060",
                "market_data": {
                    "ltp": 0.3,
                    "volume": 22315725,
                    "oi": 5636475,
                    "close_price": 0.35,
                    "bid_price": 0.3,
                    "bid_qty": 1979400,
                    "ask_price": 0.35,
                    "ask_qty": 2152500,
                    "prev_oi": 5797500
                },
                "option_greeks": {
                    "vega": 0.0568,
                    "theta": -1.2461,
                    "gamma": 0,
                    "delta": -0.0013,
                    "iv": 50.78,
                    "pop": 0.15
                }
            }
        }
    ]
}

2. Market Quote Response (/v2/market-quote/quotes):
{
    "status": "success",
    "data": {
        "NSE_INDEX:Nifty 50": {
            "ohlc": {"open": 53.4, "high": 53.8, "low": 51.75, "close": 52.05},
            "timestamp": "2023-10-19T05:21:51.099+05:30",
            "instrument_token": "NSE_INDEX|Nifty 50",
            "symbol": "NIFTY 50",
            "last_price": 22976.2,
            "volume": 0,
            "average_price": 0,
            "oi": 0,
            "net_change": -1.05
        }
    }
}

3. Intraday Candle Response (/v3/historical-candle/intraday):
{
    "status": "success",
    "data": {
        "candles": [
            ["2025-01-12T15:15:00+05:30", 2305.3, 2307.05, 2301, 2304.65, 559982, 0],
            ["2025-01-12T14:45:00+05:30", 2309.1, 2310.75, 2305.25, 2305.3, 740124, 0]
        ]
    }
}
Candle format: [Timestamp, Open, High, Low, Close, Volume, OI]

4. Option Contracts Response (/v2/option/contract):
{
    "status": "success",
    "data": [
        {
            "name": "NIFTY",
            "segment": "NSE_FO",
            "exchange": "NSE",
            "expiry": "2024-02-15",
            "instrument_key": "NSE_FO|37590",
            "trading_symbol": "NIFTY 19650 CE 15 FEB 24",
            "lot_size": 50,
            "instrument_type": "CE",
            "strike_price": 19650,
            "weekly": true
        }
    ]
}
"""

import logging
import aiohttp
import asyncio
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple, Any
from urllib.parse import quote

from config import UPSTOX_CONFIG
from indicators import StrikeData, CandleData

logger = logging.getLogger(__name__)


class UpstoxDataFetcher:
    """Fetches market data from Upstox API."""
    
    # Index symbols mapping
    INDEX_SYMBOLS = {
        "NIFTY": "NSE_INDEX|Nifty 50",
        "BANKNIFTY": "NSE_INDEX|Nifty Bank",
        "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
        "SENSEX": "BSE_INDEX|SENSEX",
        "MIDCPNIFTY": "NSE_INDEX|NIFTY MID SELECT",
    }
    
    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token or UPSTOX_CONFIG.access_token
        self.base_url = UPSTOX_CONFIG.base_url
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Default instrument key
        self.nifty_index_key = "NSE_INDEX|Nifty 50"
        
    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.access_token}",
        }
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def _make_request(self, url: str, params: Optional[Dict] = None) -> Dict:
        """Make an API request and return the response."""
        try:
            session = await self._get_session()
            async with session.get(url, headers=self._get_headers(), params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("status") == "success":
                        return data
                    else:
                        logger.error(f"API returned error: {data}")
                        return {}
                else:
                    error_text = await response.text()
                    logger.error(f"API request failed: {response.status} - {error_text}")
                    return {}
        except Exception as e:
            logger.error(f"Error making API request: {e}")
            return {}
    
    async def get_nearest_expiry(self, option_prefix: str = "NIFTY") -> Optional[str]:
        """
        Get the nearest expiry date for options.
        
        Args:
            option_prefix: Option symbol prefix (NIFTY, BANKNIFTY, SENSEX, etc.)
        
        Returns:
            Expiry date in YYYY-MM-DD format
        """
        index_key = self.INDEX_SYMBOLS.get(option_prefix, self.nifty_index_key)
        url = f"{self.base_url}/option/contract"
        params = {"instrument_key": index_key}
        
        response = await self._make_request(url, params)
        
        if not response or "data" not in response:
            logger.error(f"Failed to fetch option contracts for {option_prefix}")
            return None
        
        contracts = response["data"]
        if not contracts:
            return None
        
        # Get unique expiry dates and find nearest
        expiries = set()
        for contract in contracts:
            expiry = contract.get("expiry")
            if expiry:
                expiries.add(expiry)
        
        if not expiries:
            return None
        
        # Sort and return nearest
        sorted_expiries = sorted(expiries)
        today = date.today().isoformat()
        
        for expiry in sorted_expiries:
            if expiry >= today:
                logger.info(f"Nearest expiry for {option_prefix}: {expiry}")
                return expiry
        
        return sorted_expiries[0] if sorted_expiries else None
    
    async def get_option_chain(
        self, 
        expiry_date: str,
        index_symbol: str = None,
    ) -> Tuple[List[StrikeData], float]:
        """
        Fetch option chain data for a specific index.
        
        Args:
            expiry_date: Expiry date in YYYY-MM-DD format
            index_symbol: Index symbol (e.g., "NSE_INDEX|Nifty 50")
            
        Returns:
            Tuple of (list of StrikeData, spot_price)
        """
        if index_symbol is None:
            index_symbol = self.nifty_index_key
            
        url = f"{self.base_url}/option/chain"
        params = {
            "instrument_key": index_symbol,
            "expiry_date": expiry_date,
        }
        
        response = await self._make_request(url, params)
        
        if not response or "data" not in response:
            logger.error(f"Failed to fetch option chain for {index_symbol}")
            return [], 0.0
        
        strikes_data = []
        spot_price = 0.0
        
        for strike_item in response["data"]:
            # Extract spot price from first strike
            if spot_price == 0.0:
                spot_price = strike_item.get("underlying_spot_price", 0.0)
            
            strike_price = strike_item.get("strike_price", 0)
            
            # Parse Call Options
            call_options = strike_item.get("call_options", {})
            call_market_data = call_options.get("market_data", {})
            call_greeks = call_options.get("option_greeks", {})
            
            # Parse Put Options
            put_options = strike_item.get("put_options", {})
            put_market_data = put_options.get("market_data", {})
            put_greeks = put_options.get("option_greeks", {})
            
            strike_data = StrikeData(
                strike_price=strike_price,
                call_oi=call_market_data.get("oi", 0),
                put_oi=put_market_data.get("oi", 0),
                call_volume=call_market_data.get("volume", 0),
                put_volume=put_market_data.get("volume", 0),
                call_ltp=call_market_data.get("ltp", 0.0),
                put_ltp=put_market_data.get("ltp", 0.0),
                call_iv=call_greeks.get("iv"),
                put_iv=put_greeks.get("iv"),
            )
            
            strikes_data.append(strike_data)
        
        logger.info(f"Fetched option chain with {len(strikes_data)} strikes, spot: {spot_price}")
        return strikes_data, spot_price
    
    async def get_nifty_spot_price(self) -> float:
        """
        Get current NIFTY spot price.
        
        Returns:
            Current spot price
        """
        url = f"{self.base_url}/market-quote/quotes"
        # URL encode the instrument key properly
        params = {"instrument_key": self.nifty_index_key}
        
        response = await self._make_request(url, params)
        
        if not response or "data" not in response:
            logger.error("Failed to fetch NIFTY spot price")
            return 0.0
        
        # The key in response is formatted as "NSE_INDEX:Nifty 50"
        quote_key = "NSE_INDEX:Nifty 50"
        quote_data = response["data"].get(quote_key, {})
        
        if not quote_data:
            # Try alternate key format
            for key, value in response["data"].items():
                if "nifty" in key.lower():
                    quote_data = value
                    break
        
        last_price = quote_data.get("last_price", 0.0)
        logger.info(f"NIFTY spot price: {last_price}")
        
        return last_price
    
    async def get_intraday_candles(
        self, 
        instrument_key: Optional[str] = None,
        interval: str = "1",
        unit: str = "minutes"
    ) -> List[CandleData]:
        """
        Fetch intraday candle data using V3 API.
        
        Args:
            instrument_key: Instrument key (defaults to NIFTY index)
            interval: Candle interval (1, 3, 5, 15, 30 for minutes; 1, 2 for hours)
            unit: Time unit (minutes, hours, days)
            
        Returns:
            List of CandleData objects
        """
        if instrument_key is None:
            instrument_key = self.nifty_index_key
        
        # URL encode the instrument key
        encoded_key = quote(instrument_key, safe="")
        
        # V3 API endpoint
        url = f"https://api.upstox.com/v3/historical-candle/intraday/{encoded_key}/{unit}/{interval}"
        
        try:
            session = await self._get_session()
            async with session.get(url, headers=self._get_headers()) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("status") != "success":
                        logger.error(f"Candle API error: {data}")
                        return []
                else:
                    error_text = await response.text()
                    logger.error(f"Candle API failed: {response.status} - {error_text}")
                    return []
        except Exception as e:
            logger.error(f"Error fetching candles: {e}")
            return []
        
        candles_raw = data.get("data", {}).get("candles", [])
        
        if not candles_raw:
            logger.warning("No candle data received")
            return []
        
        candles = []
        for candle in candles_raw:
            # Candle format: [Timestamp, Open, High, Low, Close, Volume, OI]
            if len(candle) >= 6:
                candle_data = CandleData(
                    timestamp=candle[0],
                    open=float(candle[1]),
                    high=float(candle[2]),
                    low=float(candle[3]),
                    close=float(candle[4]),
                    volume=int(candle[5]),
                )
                candles.append(candle_data)
        
        logger.info(f"Fetched {len(candles)} intraday candles")
        return candles
    
    async def get_full_market_data(
        self, 
        expiry_date: Optional[str] = None,
        index_symbol: str = None,
        option_prefix: str = "NIFTY",
    ) -> Dict[str, Any]:
        """
        Fetch all required market data in one call.
        
        Args:
            expiry_date: Expiry date in YYYY-MM-DD format
            index_symbol: Index symbol (e.g., "NSE_INDEX|Nifty 50")
            option_prefix: Option prefix for expiry lookup
        
        Returns:
            Dictionary with:
            - strikes_data: List of StrikeData
            - spot_price: Current spot price
            - candles: List of CandleData
            - expiry: Expiry date used
        """
        if index_symbol is None:
            index_symbol = self.INDEX_SYMBOLS.get(option_prefix, self.nifty_index_key)
        
        # Get nearest expiry if not provided
        if expiry_date is None:
            expiry_date = await self.get_nearest_expiry(option_prefix)
            if not expiry_date:
                logger.error(f"Could not determine expiry date for {option_prefix}")
                return {}
        
        # Fetch data concurrently
        option_chain_task = asyncio.create_task(
            self.get_option_chain(expiry_date, index_symbol)
        )
        candles_task = asyncio.create_task(
            self.get_intraday_candles(index_symbol)
        )
        
        strikes_data, spot_price = await option_chain_task
        candles = await candles_task
        
        # If spot price not available from option chain, fetch separately
        if spot_price == 0.0:
            spot_price = await self.get_spot_price(index_symbol)
        
        return {
            "strikes_data": strikes_data,
            "spot_price": spot_price,
            "candles": candles,
            "expiry": expiry_date,
            "timestamp": datetime.now().isoformat(),
        }
    
    async def get_spot_price(self, index_symbol: str = None) -> float:
        """
        Get current spot price for any index.
        
        Args:
            index_symbol: Index symbol (e.g., "NSE_INDEX|Nifty 50")
        
        Returns:
            Current spot price
        """
        if index_symbol is None:
            index_symbol = self.nifty_index_key
        
        url = f"{self.base_url}/market-quote/quotes"
        params = {"instrument_key": index_symbol}
        
        response = await self._make_request(url, params)
        
        if not response or "data" not in response:
            logger.error(f"Failed to fetch spot price for {index_symbol}")
            return 0.0
        
        # The key in response is formatted differently
        for key, value in response["data"].items():
            last_price = value.get("last_price", 0.0)
            if last_price > 0:
                logger.info(f"Spot price for {index_symbol}: {last_price}")
                return last_price
        
        return 0.0


# Synchronous wrapper for non-async contexts
def fetch_market_data_sync(expiry_date: Optional[str] = None) -> Dict[str, Any]:
    """Synchronous wrapper to fetch market data."""
    fetcher = UpstoxDataFetcher()
    try:
        return asyncio.run(fetcher.get_full_market_data(expiry_date))
    finally:
        asyncio.run(fetcher.close())


def fetch_candles_sync(instrument_key: str, interval: str = "5", unit: str = "minutes") -> List[CandleData]:
    """Synchronous wrapper to fetch candle data for use in Flask routes."""
    import concurrent.futures
    
    def run_async():
        async def fetch():
            fetcher = UpstoxDataFetcher()
            try:
                candles = await fetcher.get_intraday_candles(
                    instrument_key=instrument_key,
                    interval=str(interval),
                    unit=unit
                )
                await fetcher.close()
                return candles
            except Exception as e:
                logger.error(f"Error in fetch_candles_sync: {e}")
                await fetcher.close()
                return []
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(fetch())
        finally:
            loop.close()
    
    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_async)
            return future.result(timeout=15)
    except Exception as e:
        logger.error(f"fetch_candles_sync timeout or error: {e}")
        return []
