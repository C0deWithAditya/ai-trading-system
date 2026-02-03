"""
Quick test to verify Gemini AI integration is working.
"""

import asyncio
import os

# Load environment
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from ai_analyzer import GeminiAnalyzer


async def test_ai():
    api_key = os.getenv("GEMINI_API_KEY", "")
    
    print("=" * 50)
    print("🤖 GEMINI AI TEST")
    print("=" * 50)
    
    if not api_key:
        print("❌ GEMINI_API_KEY not set in .env file")
        return
    
    print(f"✓ API Key: {api_key[:20]}...{api_key[-10:]}")
    print("\n📊 Sending test market data for analysis...\n")
    
    analyzer = GeminiAnalyzer(api_key)
    
    # Sample market data for testing
    analysis = await analyzer.analyze_market(
        spot_price=23150.50,
        pcr=0.72,
        total_call_oi=15000000,
        total_put_oi=10800000,
        vwap=23120.00,
        support=23000,
        resistance=23200,
        max_pain=23100,
        top_call_oi_strikes=[(23200, 5000000), (23300, 4500000), (23400, 4000000)],
        top_put_oi_strikes=[(23000, 4800000), (22900, 4200000), (22800, 3800000)],
        oi_changes={
            'call': [(23200, 8.5), (23300, 5.2), (23150, -3.1)],
            'put': [(23000, 12.3), (22900, 6.7), (23100, -2.5)],
        }
    )
    
    await analyzer.close()
    
    print("=" * 50)
    print("📊 AI ANALYSIS RESULT")
    print("=" * 50)
    
    if analysis.get("error"):
        print(f"❌ Error: {analysis.get('error')}")
        return
    
    print(f"""
🎯 Signal: {analysis.get('signal', 'N/A')}
📈 Confidence: {analysis.get('confidence', 0)}%
💰 Entry Strike: {analysis.get('entry_strike', 'N/A')}
🎯 Target: +{analysis.get('target_points', 0)} points
🛑 Stop Loss: -{analysis.get('stop_loss_points', 0)} points
⚖️ Risk:Reward: {analysis.get('risk_reward_ratio', 'N/A')}
📊 Market Bias: {analysis.get('market_bias', 'N/A')}
🔢 Factors Aligned: {analysis.get('factors_aligned', 0)}/5

💡 AI Reasoning:
{analysis.get('reasoning', 'No reasoning available')}
""")
    
    if analysis.get('signal') in ['CALL', 'PUT'] and analysis.get('confidence', 0) >= 60:
        print("✅ This signal would trigger an alert!")
    else:
        print("⏸️ This signal would NOT trigger an alert (confidence too low or neutral)")


if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║              GEMINI AI INTEGRATION TEST                  ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    asyncio.run(test_ai())
