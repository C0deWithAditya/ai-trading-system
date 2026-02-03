"""
Check current API usage statistics.
Run this anytime to see your usage and costs.
"""

import os
import sys
import asyncio

# Load environment
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from usage_monitor import get_usage_monitor
from notifier import TelegramNotifier


async def main():
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║              📊 USAGE STATISTICS VIEWER                  ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    # Get usage monitor
    monitor = get_usage_monitor()
    
    # Print stats to console
    monitor.print_stats()
    
    # Get detailed stats
    stats = monitor.get_current_stats()
    
    print("\n📋 Detailed Breakdown:")
    print("-" * 40)
    print(f"  📅 Date: {stats['date']}")
    print(f"  🤖 Total API Calls: {stats['api_calls']}")
    print(f"  ✅ Successful: {stats['successful_calls']}")
    print(f"  ❌ Failed: {stats['failed_calls']}")
    print(f"  🎯 Signals Generated: {stats['signals_generated']}")
    print(f"  📱 Alerts Sent: {stats['alerts_sent']}")
    print("-" * 40)
    print(f"  📈 Input Tokens: {stats['input_tokens']:,}")
    print(f"  📈 Output Tokens: {stats['output_tokens']:,}")
    print(f"  📈 Total Tokens: {stats['total_tokens']:,}")
    print("-" * 40)
    print(f"  💰 Free Tier Used: {stats['free_tier_used_percent']}%")
    print(f"  💰 Remaining Free Calls: {stats['remaining_free_calls']}")
    print(f"  💰 Estimated Cost: ₹{stats['estimated_cost_inr']} (${stats['estimated_cost_usd']})")
    print("-" * 40)
    
    if stats['is_free_tier']:
        print("\n✅ STATUS: Within FREE tier - No charges!")
    else:
        print("\n⚠️ STATUS: Free tier exceeded - Charges may apply!")
    
    # Ask if user wants to send report to Telegram
    print("\n")
    send_telegram = input("Send report to Telegram? (y/n): ").strip().lower()
    
    if send_telegram == 'y':
        notifier = TelegramNotifier()
        message = monitor.get_summary_message()
        
        success = await notifier.send_message(message)
        
        if success:
            print("✅ Report sent to Telegram!")
        else:
            print("❌ Failed to send report to Telegram")
        
        await notifier.close()
    
    # Save usage
    monitor.save()
    print("\n💾 Usage data saved to usage_stats.json")


if __name__ == "__main__":
    asyncio.run(main())
