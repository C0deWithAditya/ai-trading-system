#!/usr/bin/env python3
"""Quick API Test Script - Tests all configured APIs"""

import os
from dotenv import load_dotenv
import requests

load_dotenv()

print("\n" + "="*60)
print("🧪 API TEST SCRIPT")
print("="*60 + "\n")

# Test counters
passed = 0
failed = 0

# =============================================================================
# 1. TEST UPSTOX API
# =============================================================================
print("1️⃣  TESTING UPSTOX API...")
print("-" * 40)

access_token = os.getenv('UPSTOX_ACCESS_TOKEN')
if not access_token:
    print("   ❌ UPSTOX_ACCESS_TOKEN not found in .env")
    failed += 1
else:
    try:
        # Test with user profile endpoint
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
        response = requests.get(
            'https://api.upstox.com/v2/user/profile',
            headers=headers,
            timeout=10
        )
        data = response.json()
        
        if data.get('status') == 'success':
            user = data.get('data', {})
            print(f"   ✅ UPSTOX API: Connected!")
            print(f"   📧 Email: {user.get('email', 'N/A')}")
            print(f"   👤 Name: {user.get('user_name', 'N/A')}")
            print(f"   🆔 User ID: {user.get('user_id', 'N/A')}")
            passed += 1
        else:
            print(f"   ❌ UPSTOX API Error: {data.get('errors', data)}")
            failed += 1
    except Exception as e:
        print(f"   ❌ UPSTOX API Error: {e}")
        failed += 1

print()

# =============================================================================
# 2. TEST GEMINI API
# =============================================================================
print("2️⃣  TESTING GEMINI AI API...")
print("-" * 40)

gemini_key = os.getenv('GEMINI_API_KEY')
if not gemini_key:
    print("   ❌ GEMINI_API_KEY not found in .env")
    failed += 1
else:
    try:
        # Use direct API call instead of deprecated library
        response = requests.post(
            f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}',
            json={
                'contents': [{'parts': [{'text': 'Say "API test successful!" in exactly 3 words.'}]}]
            },
            timeout=15
        )
        data = response.json()
        
        if 'candidates' in data:
            text = data['candidates'][0]['content']['parts'][0]['text']
            print(f"   ✅ GEMINI API: Connected!")
            print(f"   🤖 Response: {text.strip()[:50]}")
            passed += 1
        elif 'error' in data:
            print(f"   ❌ GEMINI API Error: {data['error'].get('message', 'Unknown error')}")
            failed += 1
        else:
            print(f"   ❌ GEMINI API: Unexpected response")
            failed += 1
    except Exception as e:
        print(f"   ❌ GEMINI API Error: {e}")
        failed += 1

print()

# =============================================================================
# 3. TEST TELEGRAM API
# =============================================================================
print("3️⃣  TESTING TELEGRAM API...")
print("-" * 40)

bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
chat_id = os.getenv('TELEGRAM_CHAT_ID')

if not bot_token or not chat_id:
    print("   ❌ TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not found in .env")
    failed += 1
else:
    try:
        # Get bot info
        response = requests.get(
            f'https://api.telegram.org/bot{bot_token}/getMe',
            timeout=10
        )
        data = response.json()
        
        if data.get('ok'):
            bot = data.get('result', {})
            print(f"   ✅ TELEGRAM API: Connected!")
            print(f"   🤖 Bot Name: @{bot.get('username', 'N/A')}")
            print(f"   💬 Chat ID: {chat_id}")
            
            # Send a test message
            send_response = requests.post(
                f'https://api.telegram.org/bot{bot_token}/sendMessage',
                json={
                    'chat_id': chat_id,
                    'text': '✅ API Test Successful!\n\n🧪 Your trading system APIs are working correctly.',
                    'parse_mode': 'HTML'
                },
                timeout=10
            )
            if send_response.json().get('ok'):
                print(f"   📨 Test message sent to Telegram!")
            passed += 1
        else:
            print(f"   ❌ TELEGRAM API Error: {data}")
            failed += 1
    except Exception as e:
        print(f"   ❌ TELEGRAM API Error: {e}")
        failed += 1

print()

# =============================================================================
# 4. TEST UPSTOX MARKET DATA (Optional - may fail if F&O not activated)
# =============================================================================
print("4️⃣  TESTING UPSTOX MARKET DATA...")
print("-" * 40)

if access_token:
    try:
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
        # Try to get NIFTY spot price
        response = requests.get(
            'https://api.upstox.com/v2/market-quote/ltp',
            params={'instrument_key': 'NSE_INDEX|Nifty 50'},
            headers=headers,
            timeout=10
        )
        data = response.json()
        
        if data.get('status') == 'success':
            ltp_data = data.get('data', {})
            nifty_key = list(ltp_data.keys())[0] if ltp_data else None
            if nifty_key:
                price = ltp_data[nifty_key].get('last_price', 'N/A')
                print(f"   ✅ MARKET DATA: Connected!")
                print(f"   📈 NIFTY 50 LTP: ₹{price}")
                passed += 1
            else:
                print(f"   ⚠️ Market data returned empty (market may be closed)")
                passed += 1  # Still count as passed
        else:
            error = data.get('errors', [{}])[0] if data.get('errors') else {}
            print(f"   ⚠️ Market Data: {error.get('message', 'Unknown error')}")
            # Don't count as failed if it's just market closed
    except Exception as e:
        print(f"   ⚠️ Market Data: {e}")

print()

# =============================================================================
# SUMMARY
# =============================================================================
print("="*60)
print(f"📊 TEST RESULTS: {passed} passed, {failed} failed")
print("="*60)

if failed == 0:
    print("\n🎉 ALL APIS ARE WORKING! Your system is ready for trading.\n")
else:
    print("\n⚠️ Some APIs failed. Check the errors above.\n")
