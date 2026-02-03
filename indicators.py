"""
Technical Indicators Module for the F&O Trading System.
Calculates PCR, OI changes, VWAP, and other indicators.
"""

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CandleData:
    """Represents a single candle."""
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class StrikeData:
    """Represents option data for a single strike."""
    strike_price: int
    call_oi: int
    put_oi: int
    call_volume: int
    put_volume: int
    call_ltp: float
    put_ltp: float
    call_iv: Optional[float] = None
    put_iv: Optional[float] = None
    call_oi_change: float = 0.0
    put_oi_change: float = 0.0


class IndicatorCalculator:
    """Calculates various trading indicators."""
    
    def __init__(self):
        self._previous_oi_snapshot: Dict[int, Tuple[int, int]] = {}  # strike -> (call_oi, put_oi)
    
    def calculate_pcr(self, strikes_data: List[StrikeData]) -> Dict[str, float]:
        """
        Calculate Put-Call Ratio from option chain data.
        
        Returns:
            Dictionary with PCR metrics:
            - pcr_oi: PCR based on Open Interest
            - pcr_volume: PCR based on Volume
            - total_call_oi: Total Call OI
            - total_put_oi: Total Put OI
        """
        if not strikes_data:
            logger.warning("No strike data available for PCR calculation")
            return {"pcr_oi": 0.0, "pcr_volume": 0.0, "total_call_oi": 0, "total_put_oi": 0}
        
        total_call_oi = sum(s.call_oi for s in strikes_data)
        total_put_oi = sum(s.put_oi for s in strikes_data)
        total_call_volume = sum(s.call_volume for s in strikes_data)
        total_put_volume = sum(s.put_volume for s in strikes_data)
        
        # Avoid division by zero
        pcr_oi = total_put_oi / total_call_oi if total_call_oi > 0 else 0.0
        pcr_volume = total_put_volume / total_call_volume if total_call_volume > 0 else 0.0
        
        logger.info(f"PCR (OI): {pcr_oi:.2f}, PCR (Volume): {pcr_volume:.2f}")
        
        return {
            "pcr_oi": round(pcr_oi, 4),
            "pcr_volume": round(pcr_volume, 4),
            "total_call_oi": total_call_oi,
            "total_put_oi": total_put_oi,
            "total_call_volume": total_call_volume,
            "total_put_volume": total_put_volume,
        }
    
    def calculate_oi_change(self, strikes_data: List[StrikeData]) -> List[StrikeData]:
        """
        Calculate OI change between current and previous snapshot.
        Updates the strike data with OI change percentages.
        
        Returns:
            Updated strikes_data with oi_change values
        """
        for strike in strikes_data:
            if strike.strike_price in self._previous_oi_snapshot:
                prev_call_oi, prev_put_oi = self._previous_oi_snapshot[strike.strike_price]
                
                # Calculate percentage change
                if prev_call_oi > 0:
                    strike.call_oi_change = ((strike.call_oi - prev_call_oi) / prev_call_oi) * 100
                if prev_put_oi > 0:
                    strike.put_oi_change = ((strike.put_oi - prev_put_oi) / prev_put_oi) * 100
            
            # Update snapshot for next iteration
            self._previous_oi_snapshot[strike.strike_price] = (strike.call_oi, strike.put_oi)
        
        return strikes_data
    
    def calculate_vwap(self, candles: List[CandleData]) -> float:
        """
        Calculate Volume Weighted Average Price from candle data.
        
        VWAP = Σ(Typical Price × Volume) / Σ(Volume)
        Typical Price = (High + Low + Close) / 3
        
        Args:
            candles: List of candle data
            
        Returns:
            VWAP value
        """
        if not candles:
            logger.warning("No candle data available for VWAP calculation")
            return 0.0
        
        total_tp_volume = 0.0
        total_volume = 0
        
        for candle in candles:
            typical_price = (candle.high + candle.low + candle.close) / 3
            total_tp_volume += typical_price * candle.volume
            total_volume += candle.volume
        
        if total_volume == 0:
            logger.warning("Total volume is zero, cannot calculate VWAP")
            return 0.0
        
        vwap = total_tp_volume / total_volume
        logger.info(f"VWAP calculated: {vwap:.2f}")
        
        return round(vwap, 2)
    
    def find_atm_strike(self, spot_price: float, strike_gap: int = 50) -> int:
        """
        Find the At-The-Money strike based on spot price.
        
        Args:
            spot_price: Current NIFTY spot price
            strike_gap: Gap between strikes (default 50 for NIFTY)
            
        Returns:
            ATM strike price
        """
        return round(spot_price / strike_gap) * strike_gap
    
    def find_max_oi_strikes(
        self, 
        strikes_data: List[StrikeData], 
        top_n: int = 3
    ) -> Dict[str, List[Tuple[int, int]]]:
        """
        Find strikes with maximum open interest.
        
        Returns:
            Dictionary with top N strikes for calls and puts:
            - max_call_oi: [(strike, oi), ...]
            - max_put_oi: [(strike, oi), ...]
        """
        sorted_by_call_oi = sorted(strikes_data, key=lambda x: x.call_oi, reverse=True)[:top_n]
        sorted_by_put_oi = sorted(strikes_data, key=lambda x: x.put_oi, reverse=True)[:top_n]
        
        return {
            "max_call_oi": [(s.strike_price, s.call_oi) for s in sorted_by_call_oi],
            "max_put_oi": [(s.strike_price, s.put_oi) for s in sorted_by_put_oi],
        }
    
    def find_max_oi_change_strikes(
        self, 
        strikes_data: List[StrikeData], 
        top_n: int = 3
    ) -> Dict[str, List[Tuple[int, float]]]:
        """
        Find strikes with maximum OI change.
        
        Returns:
            Dictionary with top N strikes by OI change:
            - max_call_oi_change: [(strike, change%), ...]
            - max_put_oi_change: [(strike, change%), ...]
        """
        sorted_by_call_change = sorted(
            strikes_data, 
            key=lambda x: abs(x.call_oi_change), 
            reverse=True
        )[:top_n]
        
        sorted_by_put_change = sorted(
            strikes_data, 
            key=lambda x: abs(x.put_oi_change), 
            reverse=True
        )[:top_n]
        
        return {
            "max_call_oi_change": [(s.strike_price, s.call_oi_change) for s in sorted_by_call_change],
            "max_put_oi_change": [(s.strike_price, s.put_oi_change) for s in sorted_by_put_change],
        }
    
    def calculate_max_pain(self, strikes_data: List[StrikeData]) -> Optional[int]:
        """
        Calculate Max Pain strike - the strike where option writers have
        minimum loss (or where option buyers have maximum loss).
        
        Returns:
            Max Pain strike price
        """
        if not strikes_data:
            return None
        
        min_pain = float('inf')
        max_pain_strike = None
        
        for test_strike in strikes_data:
            total_pain = 0
            
            for strike in strikes_data:
                # Calculate intrinsic value of calls if expiry at test_strike
                call_pain = max(0, test_strike.strike_price - strike.strike_price) * strike.call_oi
                # Calculate intrinsic value of puts if expiry at test_strike
                put_pain = max(0, strike.strike_price - test_strike.strike_price) * strike.put_oi
                
                total_pain += call_pain + put_pain
            
            if total_pain < min_pain:
                min_pain = total_pain
                max_pain_strike = test_strike.strike_price
        
        logger.info(f"Max Pain Strike: {max_pain_strike}")
        return max_pain_strike
    
    def get_support_resistance_from_oi(
        self, 
        strikes_data: List[StrikeData],
        spot_price: float = 0
    ) -> Dict[str, int]:
        """
        Identify support and resistance levels from OI.
        - Highest Put OI strike BELOW spot = Immediate Support
        - Highest Call OI strike ABOVE spot = Immediate Resistance
        
        Returns:
            Dictionary with support and resistance strikes
        """
        if not strikes_data:
            return {"support": 0, "resistance": 0}
        
        # If no spot price provided, use simple max OI approach
        if spot_price == 0:
            max_put_oi_strike = max(strikes_data, key=lambda x: x.put_oi)
            max_call_oi_strike = max(strikes_data, key=lambda x: x.call_oi)
            return {
                "support": max_put_oi_strike.strike_price,
                "resistance": max_call_oi_strike.strike_price,
            }
        
        # Find strikes within 500 points of spot price for more relevant S/R
        range_limit = 500
        nearby_strikes = [s for s in strikes_data 
                         if abs(s.strike_price - spot_price) <= range_limit]
        
        if not nearby_strikes:
            nearby_strikes = strikes_data  # Fallback to all strikes
        
        # Support: Highest Put OI strike BELOW current price
        puts_below = [s for s in nearby_strikes if s.strike_price < spot_price]
        if puts_below:
            support_strike = max(puts_below, key=lambda x: x.put_oi)
        else:
            support_strike = max(nearby_strikes, key=lambda x: x.put_oi)
        
        # Resistance: Highest Call OI strike ABOVE current price
        calls_above = [s for s in nearby_strikes if s.strike_price > spot_price]
        if calls_above:
            resistance_strike = max(calls_above, key=lambda x: x.call_oi)
        else:
            resistance_strike = max(nearby_strikes, key=lambda x: x.call_oi)
        
        return {
            "support": support_strike.strike_price,
            "resistance": resistance_strike.strike_price,
        }
    
    def reset_oi_snapshot(self):
        """Reset the OI snapshot for a new trading session."""
        self._previous_oi_snapshot.clear()
        logger.info("OI snapshot reset")
