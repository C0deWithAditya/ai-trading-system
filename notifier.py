"""
Telegram Notification Module for the F&O Trading System.
Sends trading alerts and system notifications via Telegram Bot API.
"""

import logging
import asyncio
from datetime import datetime
from typing import Optional
import aiohttp

from config import TELEGRAM_CONFIG

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Handles sending notifications to Telegram."""
    
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.bot_token = bot_token or TELEGRAM_CONFIG.bot_token
        self.chat_id = chat_id or TELEGRAM_CONFIG.chat_id
        self.enabled = TELEGRAM_CONFIG.enabled
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """
        Send a message to the configured Telegram chat.
        
        Args:
            message: The message text to send
            parse_mode: Message formatting (HTML or Markdown)
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        if not self.enabled:
            logger.info("Telegram notifications disabled. Message not sent.")
            return False
        
        if not self.bot_token or not self.chat_id:
            logger.error("Telegram bot_token or chat_id not configured!")
            return False
        
        try:
            session = await self._get_session()
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode,
            }
            
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    logger.info("Telegram message sent successfully")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to send Telegram message: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False
    
    def _format_timestamp(self) -> str:
        """Format current timestamp for messages."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    async def send_call_alert(
        self,
        strike: int,
        reason: str,
        pcr: float,
        oi_change: float,
        spot_price: float,
        vwap: Optional[float] = None,
    ) -> bool:
        """Send a CALL opportunity alert."""
        message = f"""
🟢 <b>CALL OPPORTUNITY DETECTED</b> 🟢

⏰ <b>Time:</b> {self._format_timestamp()}
📊 <b>Strike:</b> {strike} CE

<b>📈 Market Context:</b>
• NIFTY Spot: {spot_price:,.2f}
• PCR: {pcr:.2f}
• OI Change: {oi_change:+.2f}%
{f'• VWAP: {vwap:,.2f}' if vwap else ''}

<b>💡 Reason:</b>
{reason}

⚠️ <i>This is an automated alert. Always verify before trading.</i>

<i>Powered by Aditya Verma</i>
"""
        return await self.send_message(message)
    
    async def send_put_alert(
        self,
        strike: int,
        reason: str,
        pcr: float,
        oi_change: float,
        spot_price: float,
        vwap: Optional[float] = None,
    ) -> bool:
        """Send a PUT opportunity alert."""
        message = f"""
🔴 <b>PUT OPPORTUNITY DETECTED</b> 🔴

⏰ <b>Time:</b> {self._format_timestamp()}
📊 <b>Strike:</b> {strike} PE

<b>📈 Market Context:</b>
• NIFTY Spot: {spot_price:,.2f}
• PCR: {pcr:.2f}
• OI Change: {oi_change:+.2f}%
{f'• VWAP: {vwap:,.2f}' if vwap else ''}

<b>💡 Reason:</b>
{reason}

⚠️ <i>This is an automated alert. Always verify before trading.</i>

<i>Powered by Aditya Verma</i>
"""
        return await self.send_message(message)
    
    async def send_system_alert(self, title: str, message: str, is_error: bool = False) -> bool:
        """Send a system notification (startup, errors, etc.)."""
        emoji = "❌" if is_error else "ℹ️"
        formatted_message = f"""
{emoji} <b>{title}</b>

⏰ {self._format_timestamp()}

{message}

<i>Powered by Aditya Verma</i>
"""
        return await self.send_message(formatted_message)
    
    async def send_market_summary(
        self,
        spot_price: float,
        pcr: float,
        total_call_oi: int,
        total_put_oi: int,
        max_pain_strike: Optional[int] = None,
    ) -> bool:
        """Send a market summary notification."""
        market_bias = "BULLISH 🟢" if pcr < 0.7 else "BEARISH 🔴" if pcr > 1.3 else "NEUTRAL ⚪"
        
        message = f"""
📊 <b>NIFTY MARKET SUMMARY</b>

⏰ {self._format_timestamp()}

<b>Spot Price:</b> {spot_price:,.2f}
<b>PCR:</b> {pcr:.2f}
<b>Market Bias:</b> {market_bias}

<b>Open Interest:</b>
• Total Call OI: {total_call_oi:,}
• Total Put OI: {total_put_oi:,}
{f'• Max Pain Strike: {max_pain_strike:,}' if max_pain_strike else ''}

<i>Powered by Aditya Verma</i>
"""
        return await self.send_message(message)


# Synchronous wrapper for non-async contexts
def send_telegram_sync(message: str) -> bool:
    """Synchronous wrapper to send Telegram messages."""
    notifier = TelegramNotifier()
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If event loop is already running, create a new task
            future = asyncio.ensure_future(notifier.send_message(message))
            return False  # Can't wait for result
        else:
            return loop.run_until_complete(notifier.send_message(message))
    except RuntimeError:
        # No event loop exists
        return asyncio.run(notifier.send_message(message))
    finally:
        asyncio.run(notifier.close())
