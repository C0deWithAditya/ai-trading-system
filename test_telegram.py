"""
Quick test script to verify Telegram bot configuration.
Run this to confirm your bot can send messages.
"""

import os
import asyncio

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Note: python-dotenv not installed, using environment variables directly")

import aiohttp


async def test_telegram():
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    
    print("=" * 50)
    print("TELEGRAM BOT TEST")
    print("=" * 50)
    
    # Check configuration
    if not bot_token:
        print("❌ TELEGRAM_BOT_TOKEN not set in .env file")
        return False
    
    if not chat_id:
        print("❌ TELEGRAM_CHAT_ID not set in .env file")
        return False
    
    print(f"✓ Bot Token: {bot_token[:20]}...{bot_token[-10:]}")
    print(f"✓ Chat ID: {chat_id}")
    
    # Send test message
    print("\nSending test message...")
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    message = """
🔔 <b>TEST MESSAGE</b>

✅ Your Telegram bot is configured correctly!

This is a test from the F&O Trading System.
You will receive trading alerts here.

⏰ Time: """ + __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                result = await response.json()
                
                if response.status == 200 and result.get("ok"):
                    print("\n✅ SUCCESS! Check your Telegram - you should see a test message!")
                    return True
                else:
                    print(f"\n❌ FAILED: {result}")
                    
                    # Common error explanations
                    error_code = result.get("error_code")
                    description = result.get("description", "")
                    
                    if error_code == 401:
                        print("\n💡 The bot token is invalid. Double-check it from BotFather.")
                    elif error_code == 400 and "chat not found" in description.lower():
                        print("\n💡 Chat ID is incorrect OR you haven't started a chat with the bot yet.")
                        print("   → Open Telegram, find your bot, and click START or send a message first.")
                    elif error_code == 403:
                        print("\n💡 Bot was blocked by the user or removed from the group.")
                    
                    return False
                    
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False


def main():
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║           TELEGRAM BOT CONFIGURATION TEST                ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    # Install aiohttp if needed
    try:
        import aiohttp
    except ImportError:
        print("Installing aiohttp...")
        os.system("pip install aiohttp")
        import aiohttp
    
    asyncio.run(test_telegram())


if __name__ == "__main__":
    main()
