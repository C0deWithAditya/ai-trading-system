"""
Advanced Chart Pattern Recognition Module for F&O Trading System.
Detects candlestick patterns, chart patterns, and market trends.
"""

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class PatternType(Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class TrendType(Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    SIDEWAYS = "SIDEWAYS"


@dataclass
class PatternResult:
    """Represents a detected pattern."""
    name: str
    pattern_type: PatternType
    confidence: float  # 0-100
    description: str
    candle_index: int  # Where pattern was detected


@dataclass
class Candle:
    """Simple candle representation for pattern detection."""
    open: float
    high: float
    low: float
    close: float
    volume: int = 0
    
    @property
    def body(self) -> float:
        return abs(self.close - self.open)
    
    @property
    def upper_shadow(self) -> float:
        return self.high - max(self.open, self.close)
    
    @property
    def lower_shadow(self) -> float:
        return min(self.open, self.close) - self.low
    
    @property
    def range(self) -> float:
        return self.high - self.low
    
    @property
    def is_bullish(self) -> bool:
        return self.close > self.open
    
    @property
    def is_bearish(self) -> bool:
        return self.close < self.open


class PatternRecognition:
    """Comprehensive pattern recognition engine."""
    
    def __init__(self):
        self.detected_patterns: List[PatternResult] = []
    
    def analyze(self, candles: List[Dict]) -> Dict:
        """
        Main analysis function - detects all patterns and trends.
        
        Args:
            candles: List of candle dictionaries with open, high, low, close, volume
            
        Returns:
            Dictionary with detected patterns, trend, and EMA values
        """
        if len(candles) < 20:
            return {"patterns": [], "trend": "UNKNOWN", "ema_20": 0, "market_structure": "UNKNOWN"}
        
        # Convert to Candle objects
        candle_objs = [Candle(
            open=c.get('open', 0),
            high=c.get('high', 0),
            low=c.get('low', 0),
            close=c.get('close', 0),
            volume=c.get('volume', 0)
        ) for c in candles]
        
        # Calculate indicators
        ema_20 = self._calculate_ema(candle_objs, 20)
        ema_9 = self._calculate_ema(candle_objs, 9)
        
        # Detect trend
        trend = self._detect_trend(candle_objs, ema_20)
        
        # Detect market structure
        market_structure = self._detect_market_structure(candle_objs)
        
        # Detect candlestick patterns
        patterns = []
        patterns.extend(self._detect_single_candle_patterns(candle_objs))
        patterns.extend(self._detect_two_candle_patterns(candle_objs))
        patterns.extend(self._detect_three_candle_patterns(candle_objs))
        
        # Detect chart patterns
        patterns.extend(self._detect_chart_patterns(candle_objs))
        
        # Sort by recency and confidence
        patterns.sort(key=lambda x: (-x.candle_index, -x.confidence))
        
        return {
            "patterns": [{"name": p.name, "type": p.pattern_type.value, 
                         "confidence": p.confidence, "description": p.description} 
                        for p in patterns[:10]],  # Top 10 patterns
            "trend": trend.value,
            "ema_20": round(ema_20, 2),
            "ema_9": round(ema_9, 2),
            "market_structure": market_structure,
            "pattern_summary": self._get_pattern_summary(patterns)
        }
    
    def _calculate_ema(self, candles: List[Candle], period: int) -> float:
        """Calculate Exponential Moving Average."""
        if len(candles) < period:
            return 0
        
        closes = [c.close for c in candles]
        multiplier = 2 / (period + 1)
        
        # Start with SMA
        ema = sum(closes[:period]) / period
        
        # Calculate EMA
        for price in closes[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    def _detect_trend(self, candles: List[Candle], ema_20: float) -> TrendType:
        """Detect overall trend using EMA and price action."""
        if len(candles) < 20:
            return TrendType.SIDEWAYS
        
        current_price = candles[-1].close
        recent_closes = [c.close for c in candles[-10:]]
        
        # Price vs EMA
        price_above_ema = current_price > ema_20
        
        # Higher highs/lows analysis
        recent_highs = [c.high for c in candles[-10:]]
        recent_lows = [c.low for c in candles[-10:]]
        
        higher_highs = all(recent_highs[i] >= recent_highs[i-1] for i in range(1, len(recent_highs)))
        lower_lows = all(recent_lows[i] <= recent_lows[i-1] for i in range(1, len(recent_lows)))
        
        # Range analysis for sideways
        price_range = max(recent_highs) - min(recent_lows)
        avg_price = sum(recent_closes) / len(recent_closes)
        range_percent = (price_range / avg_price) * 100
        
        if range_percent < 0.5:  # Less than 0.5% range = sideways
            return TrendType.SIDEWAYS
        
        if price_above_ema and not lower_lows:
            return TrendType.BULLISH
        elif not price_above_ema and not higher_highs:
            return TrendType.BEARISH
        else:
            return TrendType.SIDEWAYS
    
    def _detect_market_structure(self, candles: List[Candle]) -> str:
        """Detect market structure - Uptrend, Downtrend, or Range."""
        if len(candles) < 20:
            return "UNKNOWN"
        
        recent = candles[-20:]
        highs = [c.high for c in recent]
        lows = [c.low for c in recent]
        
        # Count higher highs and lower lows
        hh_count = sum(1 for i in range(1, len(highs)) if highs[i] > highs[i-1])
        ll_count = sum(1 for i in range(1, len(lows)) if lows[i] < lows[i-1])
        
        if hh_count > 12:
            return "UPTREND - Higher Highs"
        elif ll_count > 12:
            return "DOWNTREND - Lower Lows"
        else:
            return "RANGE - Consolidation"
    
    # ==================== SINGLE CANDLE PATTERNS ====================
    
    def _detect_single_candle_patterns(self, candles: List[Candle]) -> List[PatternResult]:
        """Detect single candlestick patterns."""
        patterns = []
        if len(candles) < 5:
            return patterns
        
        for i in range(len(candles) - 5, len(candles)):
            c = candles[i]
            avg_body = sum(candles[j].body for j in range(max(0, i-10), i)) / min(10, i) if i > 0 else c.body
            
            # Doji
            if c.body < c.range * 0.1 and c.range > 0:
                if c.upper_shadow > c.range * 0.4 and c.lower_shadow > c.range * 0.4:
                    patterns.append(PatternResult("Long-Legged Doji", PatternType.NEUTRAL, 70,
                        "Indecision - wait for confirmation", i))
                elif c.lower_shadow > c.body * 2 and c.upper_shadow < c.body:
                    patterns.append(PatternResult("Dragonfly Doji", PatternType.BULLISH, 75,
                        "Bullish reversal signal at support", i))
                elif c.upper_shadow > c.body * 2 and c.lower_shadow < c.body:
                    patterns.append(PatternResult("Gravestone Doji", PatternType.BEARISH, 75,
                        "Bearish reversal signal at resistance", i))
                else:
                    patterns.append(PatternResult("Doji", PatternType.NEUTRAL, 60,
                        "Market indecision", i))
            
            # Hammer (at potential support)
            elif c.lower_shadow > c.body * 2 and c.upper_shadow < c.body * 0.5:
                if i >= 3 and all(candles[i-j].close < candles[i-j-1].close for j in range(1, min(3, i))):
                    patterns.append(PatternResult("Hammer", PatternType.BULLISH, 80,
                        "Strong bullish reversal - buyers stepping in", i))
            
            # Inverted Hammer
            elif c.upper_shadow > c.body * 2 and c.lower_shadow < c.body * 0.5:
                if i >= 3 and all(candles[i-j].close < candles[i-j-1].close for j in range(1, min(3, i))):
                    patterns.append(PatternResult("Inverted Hammer", PatternType.BULLISH, 70,
                        "Potential reversal - needs confirmation", i))
            
            # Hanging Man (at potential resistance)
            elif c.lower_shadow > c.body * 2 and c.upper_shadow < c.body * 0.5:
                if i >= 3 and all(candles[i-j].close > candles[i-j-1].close for j in range(1, min(3, i))):
                    patterns.append(PatternResult("Hanging Man", PatternType.BEARISH, 75,
                        "Bearish warning - sellers emerging", i))
            
            # Shooting Star
            elif c.upper_shadow > c.body * 2 and c.lower_shadow < c.body * 0.5:
                if i >= 3 and all(candles[i-j].close > candles[i-j-1].close for j in range(1, min(3, i))):
                    patterns.append(PatternResult("Shooting Star", PatternType.BEARISH, 80,
                        "Strong bearish reversal from resistance", i))
            
            # Marubozu (strong momentum)
            elif c.body > avg_body * 1.5 and c.upper_shadow < c.body * 0.1 and c.lower_shadow < c.body * 0.1:
                if c.is_bullish:
                    patterns.append(PatternResult("Bullish Marubozu", PatternType.BULLISH, 85,
                        "Strong bullish momentum - buyers in control", i))
                else:
                    patterns.append(PatternResult("Bearish Marubozu", PatternType.BEARISH, 85,
                        "Strong bearish momentum - sellers in control", i))
            
            # Spinning Top
            elif c.body < c.range * 0.3 and c.upper_shadow > c.body and c.lower_shadow > c.body:
                patterns.append(PatternResult("Spinning Top", PatternType.NEUTRAL, 55,
                    "Indecision - wait for direction", i))
        
        return patterns
    
    # ==================== TWO CANDLE PATTERNS ====================
    
    def _detect_two_candle_patterns(self, candles: List[Candle]) -> List[PatternResult]:
        """Detect two-candlestick patterns."""
        patterns = []
        if len(candles) < 2:
            return patterns
        
        for i in range(len(candles) - 3, len(candles) - 1):
            if i < 0:
                continue
            c1, c2 = candles[i], candles[i + 1]
            
            # Bullish Engulfing
            if c1.is_bearish and c2.is_bullish:
                if c2.open < c1.close and c2.close > c1.open:
                    patterns.append(PatternResult("Bullish Engulfing", PatternType.BULLISH, 85,
                        "Strong reversal - buyers overwhelming sellers", i + 1))
            
            # Bearish Engulfing
            if c1.is_bullish and c2.is_bearish:
                if c2.open > c1.close and c2.close < c1.open:
                    patterns.append(PatternResult("Bearish Engulfing", PatternType.BEARISH, 85,
                        "Strong reversal - sellers overwhelming buyers", i + 1))
            
            # Bullish Harami
            if c1.is_bearish and c2.is_bullish:
                if c2.open > c1.close and c2.close < c1.open and c2.body < c1.body * 0.5:
                    patterns.append(PatternResult("Bullish Harami", PatternType.BULLISH, 70,
                        "Potential reversal - momentum weakening", i + 1))
            
            # Bearish Harami
            if c1.is_bullish and c2.is_bearish:
                if c2.open < c1.close and c2.close > c1.open and c2.body < c1.body * 0.5:
                    patterns.append(PatternResult("Bearish Harami", PatternType.BEARISH, 70,
                        "Potential reversal - momentum weakening", i + 1))
            
            # Tweezer Bottom
            if abs(c1.low - c2.low) < c1.range * 0.1:
                if c1.is_bearish and c2.is_bullish:
                    patterns.append(PatternResult("Tweezer Bottom", PatternType.BULLISH, 75,
                        "Support holding - reversal likely", i + 1))
            
            # Tweezer Top
            if abs(c1.high - c2.high) < c1.range * 0.1:
                if c1.is_bullish and c2.is_bearish:
                    patterns.append(PatternResult("Tweezer Top", PatternType.BEARISH, 75,
                        "Resistance holding - reversal likely", i + 1))
            
            # Piercing Pattern
            if c1.is_bearish and c2.is_bullish:
                if c2.open < c1.low and c2.close > (c1.open + c1.close) / 2:
                    patterns.append(PatternResult("Piercing Pattern", PatternType.BULLISH, 80,
                        "Bulls recovering - strong reversal signal", i + 1))
            
            # Dark Cloud Cover
            if c1.is_bullish and c2.is_bearish:
                if c2.open > c1.high and c2.close < (c1.open + c1.close) / 2:
                    patterns.append(PatternResult("Dark Cloud Cover", PatternType.BEARISH, 80,
                        "Bears taking control - strong reversal", i + 1))
        
        return patterns
    
    # ==================== THREE CANDLE PATTERNS ====================
    
    def _detect_three_candle_patterns(self, candles: List[Candle]) -> List[PatternResult]:
        """Detect three-candlestick patterns."""
        patterns = []
        if len(candles) < 3:
            return patterns
        
        for i in range(len(candles) - 4, len(candles) - 2):
            if i < 0:
                continue
            c1, c2, c3 = candles[i], candles[i + 1], candles[i + 2]
            
            # Morning Star
            if c1.is_bearish and c1.body > c2.body and c3.is_bullish:
                if c2.close < c1.close and c3.close > (c1.open + c1.close) / 2:
                    patterns.append(PatternResult("Morning Star", PatternType.BULLISH, 90,
                        "Strong bullish reversal - dawn of new uptrend", i + 2))
            
            # Evening Star
            if c1.is_bullish and c1.body > c2.body and c3.is_bearish:
                if c2.close > c1.close and c3.close < (c1.open + c1.close) / 2:
                    patterns.append(PatternResult("Evening Star", PatternType.BEARISH, 90,
                        "Strong bearish reversal - trend exhaustion", i + 2))
            
            # Three White Soldiers
            if c1.is_bullish and c2.is_bullish and c3.is_bullish:
                if c2.open > c1.open and c3.open > c2.open:
                    if c2.close > c1.close and c3.close > c2.close:
                        patterns.append(PatternResult("Three White Soldiers", PatternType.BULLISH, 95,
                            "Very strong bullish signal - sustained buying", i + 2))
            
            # Three Black Crows
            if c1.is_bearish and c2.is_bearish and c3.is_bearish:
                if c2.open < c1.open and c3.open < c2.open:
                    if c2.close < c1.close and c3.close < c2.close:
                        patterns.append(PatternResult("Three Black Crows", PatternType.BEARISH, 95,
                            "Very strong bearish signal - sustained selling", i + 2))
            
            # Three Inside Up
            if c1.is_bearish and c2.is_bullish and c3.is_bullish:
                if c2.open > c1.close and c2.close < c1.open and c3.close > c1.open:
                    patterns.append(PatternResult("Three Inside Up", PatternType.BULLISH, 85,
                        "Confirmed reversal - uptrend starting", i + 2))
            
            # Three Inside Down
            if c1.is_bullish and c2.is_bearish and c3.is_bearish:
                if c2.open < c1.close and c2.close > c1.open and c3.close < c1.open:
                    patterns.append(PatternResult("Three Inside Down", PatternType.BEARISH, 85,
                        "Confirmed reversal - downtrend starting", i + 2))
        
        return patterns
    
    # ==================== CHART PATTERNS ====================
    
    def _detect_chart_patterns(self, candles: List[Candle]) -> List[PatternResult]:
        """Detect larger chart patterns using swing highs/lows."""
        patterns = []
        if len(candles) < 30:
            return patterns
        
        # Get swing highs and lows
        highs = [c.high for c in candles[-50:]] if len(candles) >= 50 else [c.high for c in candles]
        lows = [c.low for c in candles[-50:]] if len(candles) >= 50 else [c.low for c in candles]
        closes = [c.close for c in candles[-50:]] if len(candles) >= 50 else [c.close for c in candles]
        
        # Double Bottom Detection
        if len(lows) >= 20:
            min1_idx = lows[:len(lows)//2].index(min(lows[:len(lows)//2]))
            min2_idx = len(lows)//2 + lows[len(lows)//2:].index(min(lows[len(lows)//2:]))
            
            if abs(lows[min1_idx] - lows[min2_idx]) < lows[min1_idx] * 0.01:  # Within 1%
                peak_between = max(highs[min1_idx:min2_idx]) if min2_idx > min1_idx else max(highs)
                if closes[-1] > peak_between:
                    patterns.append(PatternResult("Double Bottom Breakout", PatternType.BULLISH, 88,
                        "W-pattern confirmed - strong bullish reversal", len(candles) - 1))
                elif closes[-1] > lows[min1_idx]:
                    patterns.append(PatternResult("Double Bottom Forming", PatternType.BULLISH, 70,
                        "Potential W-pattern - watch for breakout above neckline", len(candles) - 1))
        
        # Double Top Detection
        if len(highs) >= 20:
            max1_idx = highs[:len(highs)//2].index(max(highs[:len(highs)//2]))
            max2_idx = len(highs)//2 + highs[len(highs)//2:].index(max(highs[len(highs)//2:]))
            
            if abs(highs[max1_idx] - highs[max2_idx]) < highs[max1_idx] * 0.01:  # Within 1%
                trough_between = min(lows[max1_idx:max2_idx]) if max2_idx > max1_idx else min(lows)
                if closes[-1] < trough_between:
                    patterns.append(PatternResult("Double Top Breakdown", PatternType.BEARISH, 88,
                        "M-pattern confirmed - strong bearish reversal", len(candles) - 1))
                elif closes[-1] < highs[max1_idx]:
                    patterns.append(PatternResult("Double Top Forming", PatternType.BEARISH, 70,
                        "Potential M-pattern - watch for breakdown", len(candles) - 1))
        
        # Rising Wedge (Bearish)
        recent_highs = highs[-15:]
        recent_lows = lows[-15:]
        if len(recent_highs) >= 10:
            high_slope = (recent_highs[-1] - recent_highs[0]) / len(recent_highs)
            low_slope = (recent_lows[-1] - recent_lows[0]) / len(recent_lows)
            if high_slope > 0 and low_slope > 0 and low_slope > high_slope:
                patterns.append(PatternResult("Rising Wedge", PatternType.BEARISH, 75,
                    "Bearish continuation/reversal - expect breakdown", len(candles) - 1))
        
        # Falling Wedge (Bullish)
        if len(recent_highs) >= 10:
            high_slope = (recent_highs[-1] - recent_highs[0]) / len(recent_highs)
            low_slope = (recent_lows[-1] - recent_lows[0]) / len(recent_lows)
            if high_slope < 0 and low_slope < 0 and high_slope < low_slope:
                patterns.append(PatternResult("Falling Wedge", PatternType.BULLISH, 75,
                    "Bullish continuation/reversal - expect breakout", len(candles) - 1))
        
        # Ascending Triangle
        if len(recent_highs) >= 10:
            high_range = max(recent_highs) - min(recent_highs)
            low_trend = (recent_lows[-1] - recent_lows[0]) / len(recent_lows)
            if high_range < max(recent_highs) * 0.005 and low_trend > 0:  # Flat top, rising bottom
                patterns.append(PatternResult("Ascending Triangle", PatternType.BULLISH, 80,
                    "Bullish consolidation - breakout imminent", len(candles) - 1))
        
        # Descending Triangle
        if len(recent_lows) >= 10:
            low_range = max(recent_lows) - min(recent_lows)
            high_trend = (recent_highs[-1] - recent_highs[0]) / len(recent_highs)
            if low_range < max(recent_lows) * 0.005 and high_trend < 0:  # Flat bottom, falling top
                patterns.append(PatternResult("Descending Triangle", PatternType.BEARISH, 80,
                    "Bearish consolidation - breakdown imminent", len(candles) - 1))
        
        # Flag Pattern Detection (continuation)
        if len(candles) >= 25:
            # Look for a strong move followed by consolidation
            prior_move = closes[-25] - closes[-15]
            consolidation_range = max(highs[-10:]) - min(lows[-10:])
            avg_price = sum(closes[-10:]) / 10
            
            if abs(prior_move) > avg_price * 0.015 and consolidation_range < avg_price * 0.008:
                if prior_move > 0:
                    patterns.append(PatternResult("Bull Flag", PatternType.BULLISH, 78,
                        "Bullish continuation - expect upside breakout", len(candles) - 1))
                else:
                    patterns.append(PatternResult("Bear Flag", PatternType.BEARISH, 78,
                        "Bearish continuation - expect downside breakout", len(candles) - 1))
        
        return patterns
    
    def _get_pattern_summary(self, patterns: List[PatternResult]) -> str:
        """Generate a summary for AI consumption."""
        if not patterns:
            return "No significant patterns detected."
        
        bullish = [p for p in patterns if p.pattern_type == PatternType.BULLISH]
        bearish = [p for p in patterns if p.pattern_type == PatternType.BEARISH]
        
        summary_parts = []
        
        if bullish:
            top_bull = max(bullish, key=lambda x: x.confidence)
            summary_parts.append(f"BULLISH: {top_bull.name} ({top_bull.confidence}%) - {top_bull.description}")
        
        if bearish:
            top_bear = max(bearish, key=lambda x: x.confidence)
            summary_parts.append(f"BEARISH: {top_bear.name} ({top_bear.confidence}%) - {top_bear.description}")
        
        # Overall bias
        bull_score = sum(p.confidence for p in bullish)
        bear_score = sum(p.confidence for p in bearish)
        
        if bull_score > bear_score * 1.3:
            summary_parts.append("PATTERN BIAS: BULLISH")
        elif bear_score > bull_score * 1.3:
            summary_parts.append("PATTERN BIAS: BEARISH")
        else:
            summary_parts.append("PATTERN BIAS: NEUTRAL")
        
        return " | ".join(summary_parts)


# Global instance
_pattern_engine = None


def get_pattern_engine() -> PatternRecognition:
    """Get or create global pattern recognition engine."""
    global _pattern_engine
    if _pattern_engine is None:
        _pattern_engine = PatternRecognition()
    return _pattern_engine
