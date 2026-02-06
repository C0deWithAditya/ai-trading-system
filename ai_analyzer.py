"""
AI Analyzer Module for the F&O Trading System.
Uses Google Gemini AI to analyze market conditions and generate trading insights.
"""

import logging
import aiohttp
import asyncio
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import pytz

from config import TRADING_CONFIG
from indicators import StrikeData
from usage_monitor import get_usage_monitor

logger = logging.getLogger(__name__)


class GeminiAnalyzer:
    """AI-powered market analyzer using Google Gemini."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self.model = "gemini-2.0-flash"  # Using Gemini 2.0 Flash
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def analyze_market(
        self,
        spot_price: float,
        pcr: float,
        total_call_oi: int,
        total_put_oi: int,
        vwap: Optional[float],
        support: int,
        resistance: int,
        max_pain: Optional[int],
        top_call_oi_strikes: List[tuple],
        top_put_oi_strikes: List[tuple],
        oi_changes: Dict[str, List[tuple]],
        index_name: str = "NIFTY 50",
        india_vix: Optional[float] = None,
        global_sentiment: str = "Neutral",
        news_context: str = "No major news",
        recent_learnings: str = "",
        pattern_summary: str = "",
    ) -> Dict[str, Any]:
        """
        Analyze market conditions using Gemini AI.
        
        Returns:
            Dictionary with AI analysis including:
            - signal: 'CALL', 'PUT', or 'NEUTRAL'
            - confidence: 0-100
            - reasoning: Detailed explanation
            - entry_strike: Recommended strike price
            - target: Price target
            - stop_loss: Stop loss level
        """
        
        # Prepare market context
        price_vs_vwap = "above" if vwap and spot_price > vwap else "below" if vwap else "unknown"
        vwap_deviation = ((spot_price - vwap) / vwap * 100) if vwap and vwap > 0 else 0
        
        # Pre-format values to avoid format specifier issues
        vwap_str = f"{vwap:,.2f}" if vwap else "N/A"
        max_pain_str = str(max_pain) if max_pain else "N/A"
        top_call_str = ", ".join([f"{s}({oi:,})" for s, oi in top_call_oi_strikes[:3]])
        top_put_str = ", ".join([f"{s}({oi:,})" for s, oi in top_put_oi_strikes[:3]])
        call_oi_changes_str = ", ".join([f"{s}({c:+.1f}%)" for s, c in oi_changes.get("call", [])[:3]])
        put_oi_changes_str = ", ".join([f"{s}({c:+.1f}%)" for s, c in oi_changes.get("put", [])[:3]])
        
        prompt = f"""You are an expert {index_name} options trader. Analyze the data and provide a BALANCED, DATA-DRIVEN recommendation. 

**CRITICAL BALANCE RULE: Give CALL signals for bullish setups AND PUT signals for bearish setups. Do NOT favor one direction over another.**

**SMART SIGNAL DETECTION:**
- PCR < 0.85 = BULLISH sentiment → Favor CALL
- PCR > 1.05 = BEARISH sentiment → Favor PUT
- Price ABOVE VWAP = BULLISH momentum → Favor CALL
- Price BELOW VWAP = BEARISH momentum → Favor PUT

## CURRENT MARKET DATA (Live) - {index_name}:
- **Spot Price**: {spot_price:,.2f}
- **PCR (Put-Call Ratio)**: {pcr:.2f}
- **Total Call OI**: {total_call_oi:,}
- **Total Put OI**: {total_put_oi:,}
- **VWAP**: {vwap_str}
- **Price vs VWAP**: {price_vs_vwap} ({vwap_deviation:+.2f}%)
- **Support (Max Put OI)**: {support}
- **Resistance (Max Call OI)**: {resistance}
- **Max Pain Strike**: {max_pain_str}

## TOP OI STRIKES:
- Highest Call OI: {top_call_str}
- Highest Put OI: {top_put_str}

## OI CHANGES (from last snapshot):
- Call OI Changes: {call_oi_changes_str}
- Put OI Changes: {put_oi_changes_str}

## MACRO CONTEXT:
- **India VIX**: {india_vix or 'N/A'}
- **Global Sentiment**: {global_sentiment}
- **News**: {news_context}

## PREVIOUS LEARNINGS:
{recent_learnings or 'First session.'}

## CHART PATTERNS DETECTED:
{pattern_summary or 'No patterns detected yet.'}

## SIGNAL DECISION RULES (FOLLOW STRICTLY):

**IMPORTANT: You are a trading assistant. Traders need clear signals. Avoid NEUTRAL unless truly uncertain.**

### WHEN TO GIVE **CALL** SIGNAL (BULLISH):
Give CALL when 2 or more of these are true:
1. PCR < 0.9 (Bullish bias)
2. Price is ABOVE VWAP
3. Bullish patterns detected (Hammer, Engulfing, Morning Star, etc.)
4. High Put OI at support = Writers expect support to hold
5. Trend is BULLISH

### WHEN TO GIVE **PUT** SIGNAL (BEARISH):
Give PUT when 2 or more of these are true:
1. PCR > 0.95 (Bearish bias)
2. Price is BELOW VWAP
3. Bearish patterns detected (Shooting Star, Engulfing, Evening Star, etc.)
4. High Call OI at resistance = Writers expect resistance to hold
5. Trend is BEARISH

### TRADE HORIZON RULES:
**SCALP** (Default - Use for most trades):
- Target: 20-30 points
- Stop Loss: 10-15 points

**HOLD** (Only for strong trends):
- Target: 60-100 points
- Stop Loss: 30-40 points

### NEUTRAL - USE SPARINGLY:
Only give NEUTRAL when PCR is 0.92-0.98 AND price is exactly at VWAP AND no clear patterns.
**Prefer giving a signal with lower confidence (50-60%) over NEUTRAL.**

## RESPOND IN THIS EXACT JSON FORMAT ONLY:

**EXAMPLE 1 - BULLISH MARKET (Give CALL):**
{{
    "signal": "CALL",
    "trade_horizon": "SCALP", 
    "confidence": 70,
    "entry_strike": {int(spot_price // 100) * 100},
    "target_points": 25,
    "stop_loss_points": 12,
    "risk_reward_ratio": "1:2",
    "reasoning": "BULLISH SETUP: 1) PCR 0.72 indicating strong buying interest 2) Price trading above VWAP (+0.2%) showing intraday strength 3) India VIX at 12.5 indicates low volatility environment favorable for option buyers 4) Put writers active at 25500 support level 5) Global markets positive with US futures up 0.3%. Technical confluence suggests upside momentum.",
    "key_levels": {{"support": {support}, "resistance": {resistance}}},
    "market_bias": "BULLISH",
    "factors_aligned": 5
}}

**EXAMPLE 2 - BEARISH MARKET (Give PUT):**
{{
    "signal": "PUT",
    "trade_horizon": "SCALP", 
    "confidence": 72,
    "entry_strike": {int(spot_price // 100) * 100},
    "target_points": 25,
    "stop_loss_points": 12,
    "risk_reward_ratio": "1:2",
    "reasoning": "BEARISH SETUP: 1) PCR at 1.15 showing aggressive call writing 2) Price below VWAP (-0.3%) indicating selling pressure 3) India VIX rising to 14.2 suggests market uncertainty 4) Heavy call OI at 25700 resistance acting as ceiling 5) Global cues mixed with Asian markets weak. Risk-off sentiment prevailing.",
    "key_levels": {{"support": {support}, "resistance": {resistance}}},
    "market_bias": "BEARISH",
    "factors_aligned": 5
}}

## CRITICAL RULES FOR REASONING:
1. **ALWAYS mention India VIX** in your reasoning (Low VIX = stable, High VIX = volatile)
2. **ALWAYS mention Global Sentiment** (US markets, Asian markets)
3. **ALWAYS mention at least 3-5 factors** supporting your signal
4. **Structure your reasoning as numbered points** for clarity
5. **Include specific numbers** (PCR value, VWAP deviation, VIX level)

## REMINDERS:
- If PCR < 0.9 AND Price > VWAP = Give **CALL** (confidence 60+)
- If PCR > 0.95 AND Price < VWAP = Give **PUT** (confidence 60+)
- Prefer SCALP (20-30 pts) for higher win rate
- Only say NEUTRAL if truly 50/50"""


        try:
            session = await self._get_session()
            url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"
            
            payload = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.3,  # Lower for more consistent analysis
                    "topP": 0.8,
                    "maxOutputTokens": 1024,
                }
            }
            
            # Estimate input tokens (rough estimate: 4 chars = 1 token)
            input_tokens = len(prompt) // 4
            
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # Extract text from response
                    text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    
                    # Estimate output tokens
                    output_tokens = len(text) // 4
                    
                    # Parse JSON from response
                    analysis = self._parse_ai_response(text)
                    analysis["timestamp"] = datetime.now().isoformat()
                    analysis["raw_response"] = text[:500]  # Keep for debugging
                    
                    # Track usage
                    signal = analysis.get("signal", "NEUTRAL")
                    signal_generated = signal in ["CALL", "PUT"]
                    get_usage_monitor().record_api_call(
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        success=True,
                        signal_generated=signal_generated,
                    )
                    
                    logger.info(f"AI Analysis: {analysis.get('signal')} with {analysis.get('confidence')}% confidence")
                    return analysis
                    
                else:
                    error_text = await response.text()
                    logger.error(f"Gemini API error: {response.status} - {error_text}")
                    
                    # Track failed call
                    get_usage_monitor().record_api_call(
                        input_tokens=input_tokens,
                        output_tokens=0,
                        success=False,
                    )
                    
                    return self._default_analysis("API error")
                    
        except Exception as e:
            logger.error(f"Error in AI analysis: {e}")
            get_usage_monitor().record_api_call(success=False)
            return self._default_analysis(str(e))
    
    def _parse_ai_response(self, text: str) -> Dict[str, Any]:
        """Parse JSON from AI response."""
        try:
            # Find JSON in response (may have markdown code blocks)
            text = text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            # Clean up the text
            text = text.strip()
            
            # Parse JSON
            analysis = json.loads(text)
            
            # Validate required fields
            required_fields = ["signal", "confidence", "reasoning"]
            for field in required_fields:
                if field not in analysis:
                    analysis[field] = "NEUTRAL" if field == "signal" else (0 if field == "confidence" else "No analysis available")
            
            return analysis
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response: {e}")
            logger.debug(f"Raw response: {text[:500]}")
            return self._default_analysis("Parse error")
    
    def _default_analysis(self, reason: str) -> Dict[str, Any]:
        """Return default analysis when AI fails."""
        return {
            "signal": "NEUTRAL",
            "confidence": 0,
            "entry_strike": 0,
            "target_points": 0,
            "stop_loss_points": 0,
            "risk_reward_ratio": "N/A",
            "reasoning": f"AI analysis unavailable: {reason}",
            "key_levels": {"support": 0, "resistance": 0},
            "market_bias": "NEUTRAL",
            "factors_aligned": 0,
            "error": reason,
        }
    
    async def generate_alert_message(
        self,
        signal: str,
        confidence: int,
        strike: int,
        spot_price: float,
        reasoning: str,
        target_points: int,
        stop_loss_points: int,
        risk_reward: str,
        pcr: float,
        vwap: Optional[float],
        support: int,
        resistance: int,
        index_name: str = "NIFTY 50",
        trade_horizon: str = "SCALP",
    ) -> str:
        """Generate a formatted alert message."""
        
        if signal == "CALL":
            emoji = "🟢"
            option_type = "CE"
            direction = "BULLISH"
        elif signal == "PUT":
            emoji = "🔴"
            option_type = "PE"
            direction = "BEARISH"
        else:
            return ""  # No alert for neutral
        
        # Pre-format VWAP to avoid format specifier issues
        vwap_str = f"{vwap:,.2f}" if vwap else "N/A"
        
        message = f"""
{emoji} <b>{index_name} AI SIGNAL - {signal}</b> {emoji}

🎯 <b>Confidence: {confidence}%</b>
⏳ <b>Horizon: {trade_horizon} (Hold: { '15-30m' if trade_horizon == 'SCALP' else '1-2 hrs' })</b>
📊 <b>Strike: {strike} {option_type}</b>

━━━━━━━━━━━━━━━━━━━━━━
📈 <b>MARKET CONTEXT - {index_name}</b>
━━━━━━━━━━━━━━━━━━━━━━
• Spot: {spot_price:,.2f}
• Direction: {direction}
• PCR: {pcr:.2f}
• VWAP: {vwap_str}
• Support: {support}
• Resistance: {resistance}

━━━━━━━━━━━━━━━━━━━━━━
🎯 <b>TRADE SETUP</b>
━━━━━━━━━━━━━━━━━━━━━━
• Target: +{target_points} points
• Stop Loss: -{stop_loss_points} points
• Risk:Reward: {risk_reward}

━━━━━━━━━━━━━━━━━━━━━━
🤖 <b>AI REASONING</b>
━━━━━━━━━━━━━━━━━━━━━━
{reasoning}

━━━━━━━━━━━━━━━━━━━━━━
⏰ {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%H:%M:%S')} | {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%d-%b-%Y')}

⚠️ <i>Disclaimer: This is an AI-generated signal for {index_name}. 
Do your own analysis before trading. Trade at your own risk.</i>
"""
        return message


# Factory function
def create_ai_analyzer(api_key: str) -> GeminiAnalyzer:
    """Create a Gemini AI analyzer instance."""
    return GeminiAnalyzer(api_key)
