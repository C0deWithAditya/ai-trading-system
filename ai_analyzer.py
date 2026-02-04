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
        
        prompt = f"""You are an expert {index_name} options trader analyzing live market data. Provide a specific trading recommendation.

## CURRENT MARKET DATA (Live) - {index_name}:
- **{index_name} Spot Price**: {spot_price:,.2f}
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

## MACRO & EXTERNAL CONTEXT:
- **India VIX**: {india_vix or 'N/A'} (Measures market fear/volatility)
- **Global Sentiment**: {global_sentiment} (e.g., Dow Jones, Nasdaq futures, Gift Nifty)
- **Recent News**: {news_context}

## ANALYSIS RULES:
1. **Trend is Friend**: If Price is > VWAP, prioritize CALLs. If Price is < VWAP, prioritize PUTs.
2. **Volatility Guard**: If India VIX > 18, reduce confidence and increase stop-loss points. High VIX = High Risk.
3. **Macro Alignment**: Ensure global sentiment (Bullish/Bearish) doesn't directly contradict your signal unless there's local strength/weakness.
4. **Reversals require extreme data**: Only give a PUT signal during a BULLISH rally if PCR > 1.3 or there is massive Call OI addition at current levels. 
5. **Short Covering Risk**: If price is rising fast toward a high Call OI strike, expect a breakout (short covering), NOT a reversal.
5. **Multi-Factor Alignment**: High confidence (>80) requires: PCR alignment + Price/VWAP alignment + Significant OI support.

## RESPOND IN THIS EXACT JSON FORMAT ONLY (no other text):
{{
    "signal": "CALL",
    "confidence": 75,
    "entry_strike": 23000,
    "target_points": 30,
    "stop_loss_points": 15,
    "risk_reward_ratio": "1:2",
    "reasoning": "A comprehensive 2-3 sentence analysis combining PCR/OI data with the impact of India VIX, Global Sentiment, and News context.",
    "key_levels": {{
        "support": 22900,
        "resistance": 23100
    }},
    "market_bias": "BULLISH",
    "factors_aligned": 4
}}

IMPORTANT:
- Only give CALL or PUT signal if confidence > 55 (Allows more signals while maintaining quality)
- Be proactive on trend-following signals (alignment with VWAP and PCR).
- If signals are conflicting (e.g., Price > VWAP but PCR is high), stay NEUTRAL.
- Consider risk-reward ratio (minimum 1:1.5)
- Replace example values with your actual analysis"""

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
        index_name: str = "NIFTY 50",  # New parameter
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
