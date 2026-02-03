"""
Usage Monitor for the F&O Trading System.
Tracks API calls, tokens used, and estimated costs.
"""

import json
import logging
import os
from datetime import datetime, date
from typing import Dict, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# Gemini 2.0 Flash pricing (as of Jan 2024)
GEMINI_PRICING = {
    "input_per_million": 0.10,   # $0.10 per 1M input tokens
    "output_per_million": 0.40,  # $0.40 per 1M output tokens
    "usd_to_inr": 83.0,          # Approximate exchange rate
}

# Free tier limits
FREE_TIER_LIMITS = {
    "requests_per_day": 1500,
    "requests_per_minute": 15,
    "tokens_per_minute": 1000000,
}


@dataclass
class DailyUsage:
    """Tracks daily API usage."""
    date: str
    api_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    signals_generated: int = 0
    alerts_sent: int = 0
    
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens
    
    @property
    def estimated_cost_usd(self) -> float:
        """Calculate estimated cost in USD (if exceeding free tier)."""
        input_cost = (self.input_tokens / 1_000_000) * GEMINI_PRICING["input_per_million"]
        output_cost = (self.output_tokens / 1_000_000) * GEMINI_PRICING["output_per_million"]
        return input_cost + output_cost
    
    @property
    def estimated_cost_inr(self) -> float:
        """Calculate estimated cost in INR."""
        return self.estimated_cost_usd * GEMINI_PRICING["usd_to_inr"]
    
    @property
    def is_within_free_tier(self) -> bool:
        """Check if usage is within free tier."""
        return self.api_calls <= FREE_TIER_LIMITS["requests_per_day"]
    
    @property
    def free_tier_percentage(self) -> float:
        """Percentage of free tier used."""
        return (self.api_calls / FREE_TIER_LIMITS["requests_per_day"]) * 100


class UsageMonitor:
    """Monitors and tracks API usage."""
    
    def __init__(self, usage_file: str = "usage_stats.json"):
        self.usage_file = usage_file
        self.current_usage: Optional[DailyUsage] = None
        self.history: Dict[str, DailyUsage] = {}
        self._load_usage()
    
    def _load_usage(self):
        """Load usage data from file."""
        if os.path.exists(self.usage_file):
            try:
                with open(self.usage_file, 'r') as f:
                    data = json.load(f)
                    for date_str, usage_data in data.get("history", {}).items():
                        self.history[date_str] = DailyUsage(**usage_data)
            except Exception as e:
                logger.error(f"Error loading usage data: {e}")
        
        # Initialize today's usage
        today = date.today().isoformat()
        if today in self.history:
            self.current_usage = self.history[today]
        else:
            self.current_usage = DailyUsage(date=today)
            self.history[today] = self.current_usage
    
    def _save_usage(self):
        """Save usage data to file."""
        try:
            data = {
                "last_updated": datetime.now().isoformat(),
                "history": {
                    date_str: asdict(usage) 
                    for date_str, usage in self.history.items()
                }
            }
            with open(self.usage_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving usage data: {e}")
    
    def _ensure_today(self):
        """Ensure we're tracking today's usage."""
        today = date.today().isoformat()
        if self.current_usage is None or self.current_usage.date != today:
            if today in self.history:
                self.current_usage = self.history[today]
            else:
                self.current_usage = DailyUsage(date=today)
                self.history[today] = self.current_usage
    
    def record_api_call(
        self, 
        input_tokens: int = 0, 
        output_tokens: int = 0,
        success: bool = True,
        signal_generated: bool = False,
        alert_sent: bool = False,
    ):
        """Record an API call."""
        self._ensure_today()
        
        self.current_usage.api_calls += 1
        self.current_usage.input_tokens += input_tokens
        self.current_usage.output_tokens += output_tokens
        
        if success:
            self.current_usage.successful_calls += 1
        else:
            self.current_usage.failed_calls += 1
        
        if signal_generated:
            self.current_usage.signals_generated += 1
        
        if alert_sent:
            self.current_usage.alerts_sent += 1
        
        # Save after every 10 calls
        if self.current_usage.api_calls % 10 == 0:
            self._save_usage()
    
    def get_current_stats(self) -> Dict:
        """Get current usage statistics."""
        self._ensure_today()
        
        return {
            "date": self.current_usage.date,
            "api_calls": self.current_usage.api_calls,
            "input_tokens": self.current_usage.input_tokens,
            "output_tokens": self.current_usage.output_tokens,
            "total_tokens": self.current_usage.total_tokens,
            "successful_calls": self.current_usage.successful_calls,
            "failed_calls": self.current_usage.failed_calls,
            "signals_generated": self.current_usage.signals_generated,
            "alerts_sent": self.current_usage.alerts_sent,
            "is_free_tier": self.current_usage.is_within_free_tier,
            "free_tier_used_percent": round(self.current_usage.free_tier_percentage, 1),
            "estimated_cost_usd": round(self.current_usage.estimated_cost_usd, 4),
            "estimated_cost_inr": round(self.current_usage.estimated_cost_inr, 2),
            "remaining_free_calls": FREE_TIER_LIMITS["requests_per_day"] - self.current_usage.api_calls,
        }
    
    def get_summary_message(self) -> str:
        """Get a formatted summary message for Telegram."""
        stats = self.get_current_stats()
        
        status_emoji = "✅" if stats["is_free_tier"] else "⚠️"
        
        message = f"""
📊 <b>DAILY USAGE REPORT</b>

📅 Date: {stats['date']}

━━━━━━━━━━━━━━━━━━━━━━
🤖 <b>API USAGE</b>
━━━━━━━━━━━━━━━━━━━━━━
• Total API Calls: {stats['api_calls']}
• Successful: {stats['successful_calls']}
• Failed: {stats['failed_calls']}

━━━━━━━━━━━━━━━━━━━━━━
🎯 <b>SIGNALS</b>
━━━━━━━━━━━━━━━━━━━━━━
• Signals Generated: {stats['signals_generated']}
• Alerts Sent: {stats['alerts_sent']}

━━━━━━━━━━━━━━━━━━━━━━
📈 <b>TOKEN USAGE</b>
━━━━━━━━━━━━━━━━━━━━━━
• Input Tokens: {stats['input_tokens']:,}
• Output Tokens: {stats['output_tokens']:,}
• Total Tokens: {stats['total_tokens']:,}

━━━━━━━━━━━━━━━━━━━━━━
💰 <b>COST STATUS</b>
━━━━━━━━━━━━━━━━━━━━━━
• Free Tier: {status_emoji} {'YES' if stats['is_free_tier'] else 'EXCEEDED'}
• Free Tier Used: {stats['free_tier_used_percent']}%
• Remaining Free Calls: {stats['remaining_free_calls']}
• Estimated Cost: ₹{stats['estimated_cost_inr']} (${stats['estimated_cost_usd']})

<i>{'💚 You are within FREE tier - no charges!' if stats['is_free_tier'] else '⚠️ Free tier exceeded - charges may apply'}</i>
"""
        return message
    
    def print_stats(self):
        """Print current stats to console."""
        stats = self.get_current_stats()
        
        print("\n" + "=" * 50)
        print("📊 USAGE STATISTICS")
        print("=" * 50)
        print(f"📅 Date: {stats['date']}")
        print(f"🤖 API Calls: {stats['api_calls']} / {FREE_TIER_LIMITS['requests_per_day']} (free)")
        print(f"📈 Free Tier Used: {stats['free_tier_used_percent']}%")
        print(f"🎯 Signals Generated: {stats['signals_generated']}")
        print(f"📱 Alerts Sent: {stats['alerts_sent']}")
        print(f"💰 Estimated Cost: ₹{stats['estimated_cost_inr']}")
        
        if stats['is_free_tier']:
            print("✅ Status: Within FREE tier - No charges!")
        else:
            print("⚠️ Status: Free tier exceeded!")
        
        print("=" * 50 + "\n")
    
    def save(self):
        """Force save current usage."""
        self._save_usage()


# Global usage monitor instance
usage_monitor = UsageMonitor()


def get_usage_monitor() -> UsageMonitor:
    """Get the global usage monitor instance."""
    return usage_monitor
