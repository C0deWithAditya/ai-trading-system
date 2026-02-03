"""
Main Entry Point for the AI-Enhanced F&O Trading System.
Runs continuously, analyzing market with Gemini AI and sending Telegram alerts.
"""

import asyncio
import logging
import signal
import sys
import os
from datetime import datetime, time as dt_time
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables first
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from config import SYSTEM_CONFIG, TRADING_CONFIG, UPSTOX_CONFIG, TELEGRAM_CONFIG, AI_CONFIG, load_config
from data_fetcher import UpstoxDataFetcher
from indicators import IndicatorCalculator
from strategy import StrategyEngine, SignalType
from notifier import TelegramNotifier
from ai_analyzer import GeminiAnalyzer
from usage_monitor import get_usage_monitor
from index_config import get_index_manager, IndexConfig

# Import dashboard functions (optional)
try:
    from dashboard import add_signal, update_market_data, set_system_status
    DASHBOARD_ENABLED = True
except ImportError:
    DASHBOARD_ENABLED = False
    def add_signal(*args, **kwargs): pass
    def update_market_data(*args, **kwargs): pass
    def set_system_status(*args, **kwargs): pass

# Configure logging
logging.basicConfig(
    level=getattr(logging, SYSTEM_CONFIG.log_level),
    format="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(SYSTEM_CONFIG.log_file, mode="a"),
    ],
)

logger = logging.getLogger(__name__)


class AITradingSystem:
    """
    AI-Enhanced Trading System with Gemini integration.
    """
    
    def __init__(self):
        # Reload config to get fresh values
        global UPSTOX_CONFIG, TELEGRAM_CONFIG, TRADING_CONFIG, SYSTEM_CONFIG, AI_CONFIG
        UPSTOX_CONFIG, TELEGRAM_CONFIG, TRADING_CONFIG, SYSTEM_CONFIG, AI_CONFIG = load_config()
        
        self.data_fetcher = UpstoxDataFetcher()
        self.indicator_calc = IndicatorCalculator()
        self.strategy = StrategyEngine(self.indicator_calc)
        self.notifier = TelegramNotifier()
        
        # Index manager for multi-index support
        self.index_manager = get_index_manager()
        
        # AI Analyzer
        self.ai_analyzer = None
        if AI_CONFIG.enabled and AI_CONFIG.api_key:
            self.ai_analyzer = GeminiAnalyzer(AI_CONFIG.api_key)
            logger.info("🤖 AI Analyzer (Gemini) enabled")
        else:
            logger.warning("⚠️ AI Analyzer disabled - no API key or disabled in config")
        
        # Usage monitor
        self.usage_monitor = get_usage_monitor()
        
        self._running = False
        self._expiry_dates: dict = {}  # Expiry dates per index
        self._last_signals: dict = {}  # signal_key -> timestamp (for time-based deduplication)
        
        # Market hours (IST)
        self.market_open = dt_time(9, 15)
        self.market_close = dt_time(15, 30)
    
    def is_market_hours(self) -> bool:
        """Check if current time is within market hours."""
        now = datetime.now().time()
        return self.market_open <= now <= self.market_close
    
    async def initialize(self):
        """Initialize the trading system."""
        logger.info("=" * 60)
        logger.info("🚀 MULTI-INDEX AI-ENHANCED F&O TRADING SYSTEM")
        logger.info("=" * 60)
        
        # Validate configuration
        if not UPSTOX_CONFIG.access_token or UPSTOX_CONFIG.access_token == "your_access_token_here":
            logger.error("❌ UPSTOX_ACCESS_TOKEN not configured!")
            logger.error("Please generate an access token and update .env file")
            return False
        
        if not AI_CONFIG.api_key:
            logger.warning("⚠️ Gemini API key not configured - AI analysis disabled")
        
        # Get enabled indices
        enabled_indices = self.index_manager.get_enabled_indices()
        if not enabled_indices:
            logger.error("❌ No indices enabled! Enable at least one index.")
            return False
        
        logger.info(f"📊 Enabled indices: {', '.join([idx.display_name for idx in enabled_indices])}")
        
        # Get nearest expiry for each enabled index
        for index_config in enabled_indices:
            try:
                expiry = await self.data_fetcher.get_nearest_expiry(index_config.option_symbol_prefix)
                if expiry:
                    self._expiry_dates[index_config.name] = expiry
                    logger.info(f"📅 {index_config.display_name} expiry: {expiry}")
                else:
                    logger.warning(f"⚠️ Could not fetch expiry for {index_config.display_name}")
            except Exception as e:
                logger.warning(f"⚠️ Error fetching expiry for {index_config.display_name}: {e}")
        
        if not self._expiry_dates:
            logger.error("Could not fetch expiry date for any index")
            return False
        
        logger.info(f"🤖 AI Analysis: {'Enabled' if self.ai_analyzer else 'Disabled'}")
        logger.info(f"🎯 Min Confidence: {AI_CONFIG.min_confidence}%")
        
        # Send startup notification
        indices_list = "\n".join([f"• {idx.display_name}" for idx in enabled_indices])
        if TELEGRAM_CONFIG.enabled and TELEGRAM_CONFIG.bot_token:
            await self.notifier.send_message(f"""
🚀 <b>Multi-Index AI Trading System Started</b>

📊 <b>Active Indices:</b>
{indices_list}

🤖 AI: {'Gemini Enabled' if self.ai_analyzer else 'Disabled'}
🎯 Min Confidence: {AI_CONFIG.min_confidence}%
⏰ Interval: {SYSTEM_CONFIG.refresh_interval_seconds}s

<i>System is now monitoring multiple indices...</i>
""")
        
        logger.info("✅ System initialized successfully")
        set_system_status("Running")
        return True
    
    async def run_ai_analysis_cycle(self):
        """Run a single analysis cycle for all enabled indices."""
        try:
            logger.info("-" * 50)
            logger.info(f"🔄 Analysis cycle at {datetime.now().strftime('%H:%M:%S')}")
            
            # Analyze each enabled index
            enabled_indices = self.index_manager.get_enabled_indices()
            
            for index_config in enabled_indices:
                if index_config.name not in self._expiry_dates:
                    continue
                    
                try:
                    await self._analyze_single_index(index_config)
                except Exception as e:
                    logger.error(f"Error analyzing {index_config.display_name}: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Error in analysis cycle: {e}", exc_info=True)
    
    async def _analyze_single_index(self, index_config: IndexConfig):
        """Analyze a single index."""
        index_name = index_config.name
        expiry_date = self._expiry_dates.get(index_name)
        
        if not expiry_date:
            return
        
        logger.info(f"📊 Analyzing {index_config.display_name}...")
        
        # Fetch market data for this index
        market_data = await self.data_fetcher.get_full_market_data(
            expiry_date, 
            index_symbol=index_config.symbol,
            option_prefix=index_config.option_symbol_prefix
        )
        
        if not market_data or not market_data.get("strikes_data"):
            logger.warning(f"⚠️ No data for {index_config.display_name}, skipping")
            return
        
        strikes_data = market_data["strikes_data"]
        spot_price = market_data["spot_price"]
        candles = market_data["candles"]
        
        logger.info(f"📊 {index_config.display_name}: {spot_price:,.2f}")
        
        # Calculate indicators
        pcr_data = self.indicator_calc.calculate_pcr(strikes_data)
        strikes_data = self.indicator_calc.calculate_oi_change(strikes_data)
        vwap = self.indicator_calc.calculate_vwap(candles) if candles else None
        sr_levels = self.indicator_calc.get_support_resistance_from_oi(strikes_data, spot_price)
        max_pain = self.indicator_calc.calculate_max_pain(strikes_data)
        
        # Get top OI strikes
        top_oi = self.indicator_calc.find_max_oi_strikes(strikes_data)
        oi_changes = self.indicator_calc.find_max_oi_change_strikes(strikes_data)
        
        vwap_str = f"{vwap:,.2f}" if vwap else "N/A"
        logger.info(f"📈 {index_name} PCR: {pcr_data['pcr_oi']:.2f} | VWAP: {vwap_str}")
        
        # Update dashboard with market data for this index
        update_market_data(index_name, {
            "spot_price": spot_price,
            "pcr": pcr_data['pcr_oi'],
            "vwap": vwap or 0,
            "support": sr_levels['support'],
            "resistance": sr_levels['resistance'],
            "candles": [
                {
                    "timestamp": c.timestamp,
                    "open": c.open,
                    "high": c.high,
                    "low": c.low,
                    "close": c.close,
                    "volume": c.volume
                } for c in candles
            ] if candles else []
        })
        
        # AI Analysis
        if self.ai_analyzer:
            await self._run_ai_analysis(
                index_name=index_name,
                index_display_name=index_config.display_name,
                spot_price=spot_price,
                pcr=pcr_data['pcr_oi'],
                total_call_oi=pcr_data['total_call_oi'],
                total_put_oi=pcr_data['total_put_oi'],
                vwap=vwap,
                support=sr_levels['support'],
                resistance=sr_levels['resistance'],
                max_pain=max_pain,
                top_call_oi=top_oi['max_call_oi'],
                top_put_oi=top_oi['max_put_oi'],
                oi_changes={
                    'call': oi_changes['max_call_oi_change'],
                    'put': oi_changes['max_put_oi_change'],
                }
            )
        else:
            # Fallback to rule-based strategy
            await self._run_rule_based_analysis(
                index_name, spot_price, strikes_data, pcr_data, vwap
            )
    
    async def _run_ai_analysis(
        self,
        index_name: str,
        index_display_name: str,
        spot_price: float,
        pcr: float,
        total_call_oi: int,
        total_put_oi: int,
        vwap: Optional[float],
        support: int,
        resistance: int,
        max_pain: Optional[int],
        top_call_oi: list,
        top_put_oi: list,
        oi_changes: dict,
    ):
        """Run AI-powered analysis for a specific index."""
        logger.info(f"🤖 Running AI analysis for {index_display_name}...")
        
        analysis = await self.ai_analyzer.analyze_market(
            spot_price=spot_price,
            pcr=pcr,
            total_call_oi=total_call_oi,
            total_put_oi=total_put_oi,
            vwap=vwap,
            support=support,
            resistance=resistance,
            max_pain=max_pain,
            top_call_oi_strikes=top_call_oi,
            top_put_oi_strikes=top_put_oi,
            oi_changes=oi_changes,
            index_name=index_display_name,  # Pass index name to AI
        )
        
        signal = analysis.get("signal", "NEUTRAL")
        confidence = analysis.get("confidence", 0)
        reasoning = analysis.get("reasoning", "No reasoning provided")
        
        logger.info(f"🎯 {index_name} AI Signal: {signal} | Confidence: {confidence}%")
        logger.info(f"💡 Reasoning: {reasoning[:100]}...")
        
        # Send alert if confidence meets threshold
        if signal in ["CALL", "PUT"] and confidence >= AI_CONFIG.min_confidence:
            signal_key = f"{index_name}_{signal}_{analysis.get('entry_strike', 0)}"
            
            # Allow same signal if 10 minutes have passed since last one
            current_time = datetime.now()
            last_signal_time = self._last_signals.get(signal_key)
            time_threshold = 600  # 10 minutes in seconds
            
            should_send = (
                last_signal_time is None or 
                (current_time - last_signal_time).total_seconds() > time_threshold
            )
            
            if should_send:
                # Generate and send alert with index name
                alert_message = await self.ai_analyzer.generate_alert_message(
                    signal=signal,
                    confidence=confidence,
                    strike=analysis.get("entry_strike", 0),
                    spot_price=spot_price,
                    reasoning=reasoning,
                    target_points=analysis.get("target_points", 0),
                    stop_loss_points=analysis.get("stop_loss_points", 0),
                    risk_reward=analysis.get("risk_reward_ratio", "N/A"),
                    pcr=pcr,
                    vwap=vwap,
                    support=support,
                    resistance=resistance,
                    index_name=index_display_name,  # Add index name
                )
                
                if alert_message:
                    await self.notifier.send_message(alert_message)
                    logger.info(f"📱 {index_name} Alert sent: {signal} at strike {analysis.get('entry_strike')}")
                    self._last_signals[signal_key] = current_time
                    
                    # Track alert sent
                    self.usage_monitor.current_usage.alerts_sent += 1
                    
                    # Add signal to dashboard with index
                    add_signal({
                        "index": index_name,
                        "signal": signal,
                        "strike": analysis.get("entry_strike", 0),
                        "confidence": confidence,
                        "reasoning": reasoning[:100] + "..." if len(reasoning) > 100 else reasoning,
                        "target": analysis.get("target_points", 0),
                        "stop_loss": analysis.get("stop_loss_points", 0),
                    })
        else:
            logger.info(f"⏸️ {index_name} No alert - Signal: {signal}, Confidence: {confidence}%")
        
        # Clear old signals periodically
        if len(self._last_signals) > 100:
            self._last_signals.clear()
    
    async def _run_rule_based_analysis(self, index_name, spot_price, strikes_data, pcr_data, vwap):
        """Fallback to rule-based strategy."""
        logger.info("📊 Running rule-based analysis (AI disabled)")
        
        signals = self.strategy.analyze(
            spot_price=spot_price,
            strikes_data=strikes_data,
            pcr_data=pcr_data,
            vwap=vwap,
        )
        
        for signal in signals:
            if signal.confidence >= 0.4:
                reason = "\n".join(f"• {r}" for r in signal.reasons)
                
                if signal.signal_type == SignalType.CALL:
                    await self.notifier.send_call_alert(
                        strike=signal.strike,
                        reason=reason,
                        pcr=pcr_data['pcr_oi'],
                        oi_change=signal.oi_change,
                        spot_price=spot_price,
                        vwap=vwap,
                    )
                elif signal.signal_type == SignalType.PUT:
                    await self.notifier.send_put_alert(
                        strike=signal.strike,
                        reason=reason,
                        pcr=pcr_data['pcr_oi'],
                        oi_change=signal.oi_change,
                        spot_price=spot_price,
                        vwap=vwap,
                    )
    
    async def run(self):
        """Main run loop."""
        if not await self.initialize():
            logger.error("❌ Failed to initialize trading system")
            return
        
        self._running = True
        logger.info(f"🔄 Starting main loop with {SYSTEM_CONFIG.refresh_interval_seconds}s interval")
        
        while self._running:
            try:
                if self.is_market_hours():
                    await self.run_ai_analysis_cycle()
                else:
                    current_time = datetime.now().strftime('%H:%M:%S')
                    logger.info(f"⏸️ Market closed ({current_time}). Waiting...")
                
                await asyncio.sleep(SYSTEM_CONFIG.refresh_interval_seconds)
                
            except asyncio.CancelledError:
                logger.info("Received cancellation signal")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                await asyncio.sleep(SYSTEM_CONFIG.refresh_interval_seconds)
        
        await self.shutdown()
    
    async def shutdown(self):
        """Graceful shutdown."""
        logger.info("🛑 Shutting down trading system...")
        self._running = False
        set_system_status("Stopped")
        
        # Save usage and send summary
        self.usage_monitor.save()
        self.usage_monitor.print_stats()
        
        if TELEGRAM_CONFIG.enabled and TELEGRAM_CONFIG.bot_token:
            # Send usage summary
            usage_summary = self.usage_monitor.get_summary_message()
            await self.notifier.send_message(usage_summary)
            
            await self.notifier.send_message("🛑 <b>AI Trading System Stopped</b>\n\nThe trading system has been stopped.")
        
        await self.data_fetcher.close()
        await self.notifier.close()
        if self.ai_analyzer:
            await self.ai_analyzer.close()
        
        logger.info("✅ Shutdown complete")
    
    def stop(self):
        """Signal the system to stop."""
        self._running = False


def setup_signal_handlers(system: AITradingSystem):
    """Setup signal handlers for graceful shutdown."""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}")
        system.stop()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def main():
    """Entry point."""
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║        🤖 AI-ENHANCED F&O TRADING SYSTEM 🤖                 ║
    ║           NIFTY OPTIONS - Powered by Aditya Verma           ║
    ╠══════════════════════════════════════════════════════════════╣
    ║  Features:                                                   ║
    ║  • 🤖 AI-Powered Analysis (Gemini 1.5 Flash)                ║
    ║  • 📊 Real-time Option Chain Monitoring                     ║
    ║  • 🎯 Confidence-based Signal Generation                    ║
    ║  • 📱 Instant Telegram Alerts                               ║
    ║  • 💡 AI Reasoning for Each Trade                           ║
    ║  • 🎯 Entry, Target & Stop-Loss Levels                      ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    system = AITradingSystem()
    setup_signal_handlers(system)
    
    # Start Dashboard in a separate thread
    try:
        import threading
        import os
        from dashboard import run_dashboard
        
        # Use PORT from environment (Railway sets this) or default to 8080
        port = int(os.environ.get('PORT', 8080))
        logger.info(f"🖥️ Starting Dashboard on http://0.0.0.0:{port}")
        
        t = threading.Thread(target=run_dashboard, kwargs={'host': '0.0.0.0', 'port': port})
        t.daemon = True
        t.start()
    except Exception as e:
        logger.error(f"Failed to start dashboard: {e}")
    
    try:
        asyncio.run(system.run())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
