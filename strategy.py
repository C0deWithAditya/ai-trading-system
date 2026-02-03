"""
Strategy Module for the F&O Trading System.
Implements rule-based strategy to detect CALL and PUT opportunities.
"""

import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum

from config import TRADING_CONFIG
from indicators import StrikeData, IndicatorCalculator

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Type of trading signal."""
    CALL = "CALL"
    PUT = "PUT"
    NEUTRAL = "NEUTRAL"


@dataclass
class TradingSignal:
    """Represents a trading signal/opportunity."""
    signal_type: SignalType
    strike: int
    confidence: float  # 0.0 to 1.0
    reasons: List[str]
    pcr: float
    oi_change: float
    spot_price: float
    vwap: Optional[float] = None


class StrategyEngine:
    """
    Rule-based strategy engine for detecting trading opportunities.
    
    Strategy Rules:
    
    CALL Opportunity (Bullish):
    1. PCR < 0.7 (More put writing = bullish)
    2. Significant Call OI reduction at resistance (unwinding)
    3. Significant Put OI addition at support (building support)
    4. Price above VWAP (bullish momentum)
    5. Price near support level (bounce play)
    
    PUT Opportunity (Bearish):
    1. PCR > 1.3 (More call writing = bearish)
    2. Significant Put OI reduction at support (support breaking)
    3. Significant Call OI addition at resistance (building resistance)
    4. Price below VWAP (bearish momentum)
    5. Price near resistance level (rejection play)
    """
    
    def __init__(self, indicator_calculator: Optional[IndicatorCalculator] = None):
        self.config = TRADING_CONFIG
        self.indicator_calc = indicator_calculator or IndicatorCalculator()
        self._last_signals: List[TradingSignal] = []
    
    def analyze(
        self,
        spot_price: float,
        strikes_data: List[StrikeData],
        pcr_data: Dict[str, float],
        vwap: Optional[float] = None,
    ) -> List[TradingSignal]:
        """
        Analyze market data and generate trading signals.
        
        Args:
            spot_price: Current NIFTY spot price
            strikes_data: Option chain strike data with OI changes
            pcr_data: PCR metrics from indicator calculator
            vwap: Current VWAP value
            
        Returns:
            List of trading signals (opportunities)
        """
        signals = []
        
        pcr = pcr_data.get("pcr_oi", 1.0)
        
        # Find ATM and nearby strikes
        atm_strike = self.indicator_calc.find_atm_strike(spot_price)
        atm_range = self.config.atm_strike_range
        
        nearby_strikes = [
            s for s in strikes_data 
            if abs(s.strike_price - atm_strike) <= (atm_range * 50)
        ]
        
        if not nearby_strikes:
            logger.warning("No nearby strikes found for analysis")
            return signals
        
        # Get support/resistance levels
        sr_levels = self.indicator_calc.get_support_resistance_from_oi(strikes_data)
        support = sr_levels["support"]
        resistance = sr_levels["resistance"]
        
        # Analyze each nearby strike for opportunities
        for strike in nearby_strikes:
            # Skip strikes with very low OI/volume
            if strike.call_oi < self.config.min_oi and strike.put_oi < self.config.min_oi:
                continue
            
            call_signal = self._check_call_opportunity(
                strike, spot_price, pcr, vwap, support, resistance
            )
            if call_signal:
                signals.append(call_signal)
            
            put_signal = self._check_put_opportunity(
                strike, spot_price, pcr, vwap, support, resistance
            )
            if put_signal:
                signals.append(put_signal)
        
        # Sort by confidence
        signals.sort(key=lambda x: x.confidence, reverse=True)
        
        self._last_signals = signals
        return signals
    
    def _check_call_opportunity(
        self,
        strike: StrikeData,
        spot_price: float,
        pcr: float,
        vwap: Optional[float],
        support: int,
        resistance: int,
    ) -> Optional[TradingSignal]:
        """Check if there's a CALL opportunity at this strike."""
        reasons = []
        confidence_factors = []
        
        # Rule 1: Low PCR indicates bullish sentiment
        if pcr < self.config.pcr_bullish_threshold:
            reasons.append(f"Low PCR ({pcr:.2f}) indicates bullish sentiment")
            confidence_factors.append(0.2)
        
        # Rule 2: Put OI building (support building)
        if strike.put_oi_change > self.config.oi_change_significant:
            reasons.append(f"Put OI increased by {strike.put_oi_change:.1f}% (support building)")
            confidence_factors.append(0.25)
        
        # Rule 3: Call OI reduction (call unwinding at resistance)
        if strike.strike_price >= resistance and strike.call_oi_change < -self.config.oi_change_significant:
            reasons.append(f"Call OI decreased by {abs(strike.call_oi_change):.1f}% at resistance (unwinding)")
            confidence_factors.append(0.2)
        
        # Rule 4: Price above VWAP
        if vwap and spot_price > vwap:
            deviation = ((spot_price - vwap) / vwap) * 100
            if deviation > self.config.vwap_deviation_threshold:
                reasons.append(f"Price {deviation:.2f}% above VWAP (bullish momentum)")
                confidence_factors.append(0.15)
        
        # Rule 5: Price near support (bounce play)
        support_distance = abs(spot_price - support)
        if support_distance <= 100 and spot_price >= support:
            reasons.append(f"Price near support at {support} (potential bounce)")
            confidence_factors.append(0.2)
        
        # Generate signal if we have enough confidence
        if len(confidence_factors) >= 2:  # At least 2 factors
            confidence = min(sum(confidence_factors), 1.0)
            return TradingSignal(
                signal_type=SignalType.CALL,
                strike=strike.strike_price,
                confidence=confidence,
                reasons=reasons,
                pcr=pcr,
                oi_change=strike.call_oi_change,
                spot_price=spot_price,
                vwap=vwap,
            )
        
        return None
    
    def _check_put_opportunity(
        self,
        strike: StrikeData,
        spot_price: float,
        pcr: float,
        vwap: Optional[float],
        support: int,
        resistance: int,
    ) -> Optional[TradingSignal]:
        """Check if there's a PUT opportunity at this strike."""
        reasons = []
        confidence_factors = []
        
        # Rule 1: High PCR indicates bearish sentiment
        if pcr > self.config.pcr_bearish_threshold:
            reasons.append(f"High PCR ({pcr:.2f}) indicates bearish sentiment")
            confidence_factors.append(0.2)
        
        # Rule 2: Call OI building (resistance building)
        if strike.call_oi_change > self.config.oi_change_significant:
            reasons.append(f"Call OI increased by {strike.call_oi_change:.1f}% (resistance building)")
            confidence_factors.append(0.25)
        
        # Rule 3: Put OI reduction (support breaking)
        if strike.strike_price <= support and strike.put_oi_change < -self.config.oi_change_significant:
            reasons.append(f"Put OI decreased by {abs(strike.put_oi_change):.1f}% at support (breaking)")
            confidence_factors.append(0.2)
        
        # Rule 4: Price below VWAP
        if vwap and spot_price < vwap:
            deviation = ((vwap - spot_price) / vwap) * 100
            if deviation > self.config.vwap_deviation_threshold:
                reasons.append(f"Price {deviation:.2f}% below VWAP (bearish momentum)")
                confidence_factors.append(0.15)
        
        # Rule 5: Price near resistance (rejection play)
        resistance_distance = abs(spot_price - resistance)
        if resistance_distance <= 100 and spot_price <= resistance:
            reasons.append(f"Price near resistance at {resistance} (potential rejection)")
            confidence_factors.append(0.2)
        
        # Generate signal if we have enough confidence
        if len(confidence_factors) >= 2:  # At least 2 factors
            confidence = min(sum(confidence_factors), 1.0)
            return TradingSignal(
                signal_type=SignalType.PUT,
                strike=strike.strike_price,
                confidence=confidence,
                reasons=reasons,
                pcr=pcr,
                oi_change=strike.put_oi_change,
                spot_price=spot_price,
                vwap=vwap,
            )
        
        return None
    
    def get_market_bias(self, pcr: float, spot_price: float, vwap: Optional[float]) -> str:
        """
        Determine overall market bias.
        
        Returns:
            Market bias description
        """
        bias_factors = []
        
        if pcr < self.config.pcr_bullish_threshold:
            bias_factors.append("BULLISH (Low PCR)")
        elif pcr > self.config.pcr_bearish_threshold:
            bias_factors.append("BEARISH (High PCR)")
        else:
            bias_factors.append("NEUTRAL (Normal PCR)")
        
        if vwap:
            if spot_price > vwap:
                bias_factors.append("Price above VWAP")
            else:
                bias_factors.append("Price below VWAP")
        
        return " | ".join(bias_factors)
    
    def get_last_signals(self) -> List[TradingSignal]:
        """Get the most recent signals generated."""
        return self._last_signals
