"""
Main Entry Point for the AI-Enhanced F&O Trading System.
Runs continuously, analyzing market with Gemini AI and sending Telegram alerts.
"""

import asyncio
import logging
import signal
import sys
import os
from datetime import datetime, time as dt_time, timedelta
import pytz
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
from signal_tracker import get_signal_tracker
from virtual_trader import get_virtual_trader

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
        
        # Macro data
        self.india_vix = 0.0
        self.global_sentiment = "Neutral"
        self.news_context = "No major news"
        self._last_macro_update = datetime.min
        self._eod_done_today = None # Date of last EOD analysis
    
    async def _update_macro_context(self):
        """Update global news and macro sentiment."""
        try:
            # For now, update with recent relevant events for Feb 2026
            # In a production env, this would call a News API or search tool
            self.global_sentiment = "Mixed (Bullish on Trade, Bearish on Tech)"
            self.news_context = (
                "India-US Trade Deal signed (Bullish for Pharma/Infra/Banks). "
                "Global Tech sell-off ongoing (Bearish for IT). "
                "RBI Policy meet expected Feb 6 (Wait & Watch tone). "
                "US Fed holds rates at 3.50%."
            )
            
            # Fetch real-time India VIX
            vix_price = await self.data_fetcher.get_spot_price("NSE_INDEX|India VIX")
            if vix_price > 0:
                self.india_vix = vix_price
                
            self._last_macro_update = datetime.now()
            logger.info(f"🌍 Macro context updated: VIX={self.india_vix}, Sentiment={self.global_sentiment}")
        except Exception as e:
            logger.error(f"Error updating macro context: {e}")

    def is_market_hours(self) -> bool:
        """Check if current time is within market hours (IST)."""
        timezone = pytz.timezone('Asia/Kolkata')
        now = datetime.now(timezone).time()
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
            error_msg = "❌ <b>System Startup Failed</b>\n\nCould not fetch expiry dates from Upstox. Your <b>Access Token</b> might be invalid or expired.\n\nPlease run <code>python auth_helper.py</code> to generate a new token."
            logger.error("Could not fetch expiry date for any index - Token likely invalid")
            if TELEGRAM_CONFIG.enabled and TELEGRAM_CONFIG.bot_token:
                await self.notifier.send_message(error_msg)
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
            ist = pytz.timezone('Asia/Kolkata')
            logger.info(f"🔄 Analysis cycle at {datetime.now(ist).strftime('%H:%M:%S')}")
            
            # Refresh macro context every hour
            if (datetime.now() - self._last_macro_update).total_seconds() > 3600:
                await self._update_macro_context()
            
            # Analyze each enabled index
            enabled_indices = self.index_manager.get_enabled_indices()
            
            for index_config in enabled_indices:
                if index_config.name not in self._expiry_dates:
                    continue
                    
                try:
                    await self._analyze_single_index(index_config)
                except Exception as e:
                    logger.error(f"Error analyzing {index_config.display_name}: {e}")
            
            # Send hourly performance update
            await self._send_hourly_showcase()
                    
        except Exception as e:
            logger.error(f"❌ Error in analysis cycle: {e}", exc_info=True)
    
    async def _analyze_single_index(self, index_config: IndexConfig):
        """Analyze a single index."""
        index_name = index_config.name
        expiry_date = self._expiry_dates.get(index_name)
        
        if not expiry_date:
            return
            
        # VIX and Sentiment are already updated in the main cycle
        
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
                },
                strikes_data=strikes_data,
                india_vix=self.india_vix,
                global_sentiment=self.global_sentiment,
                news_context=self.news_context,
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
        strikes_data: list = None,
        india_vix: float = 0.0,
        global_sentiment: str = "Neutral",
        news_context: str = "No major news",
    ):
        """Run AI-powered analysis for a specific index."""
        logger.info(f"🤖 Running AI analysis for {index_display_name}...")
        
        # Fetch recent learnings for self-improvement
        from performance_manager import get_performance_manager
        recent_learnings = get_performance_manager().get_recent_learnings(limit=3)
        
        # Get pattern analysis from candles
        pattern_summary = ""
        try:
            from pattern_recognition import get_pattern_engine
            # Get candles from dashboard state if available
            from dashboard import dashboard_state
            candles = dashboard_state.get("market_data", {}).get(index_name, {}).get("candles", [])
            if candles and len(candles) >= 20:
                pattern_engine = get_pattern_engine()
                pattern_analysis = pattern_engine.analyze(candles)
                pattern_summary = pattern_analysis.get("pattern_summary", "")
                trend = pattern_analysis.get("trend", "UNKNOWN")
                ema_20 = pattern_analysis.get("ema_20", 0)
                pattern_summary = f"Trend: {trend} | EMA20: {ema_20:.2f} | {pattern_summary}"
        except Exception as pe:
            logger.warning(f"Pattern analysis failed: {pe}")
        
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
            index_name=index_display_name,
            india_vix=india_vix,
            global_sentiment=global_sentiment,
            news_context=news_context,
            recent_learnings=recent_learnings,
            pattern_summary=pattern_summary
        )
        
        signal = analysis.get("signal", "NEUTRAL")
        confidence = analysis.get("confidence", 0)
        reasoning = analysis.get("reasoning", "No reasoning provided")
        
        logger.info(f"🎯 {index_name} AI Signal: {signal} | Confidence: {confidence}%")
        logger.info(f"💡 Reasoning: {reasoning[:100]}...")
        
        # Check if AI failed (quota exhausted, API error) - fall back to rule-based
        if "API error" in reasoning or "unavailable" in reasoning.lower() or confidence == 0:
            logger.warning(f"⚠️ AI failed, falling back to rule-based analysis")
            await self._run_rule_based_analysis(
                index_name, spot_price, strikes_data, 
                {"pcr_oi": pcr, "total_call_oi": total_call_oi, "total_put_oi": total_put_oi}, 
                vwap
            )
            return
        
        # ALWAYS add signals to dashboard for visibility (even low confidence)
        if signal in ["CALL", "PUT"]:
            add_signal({
                "index": index_name,
                "signal": signal,
                "strike": analysis.get("entry_strike", 0),
                "confidence": confidence,
                "reasoning": reasoning[:100] + "..." if len(reasoning) > 100 else reasoning,
                "target": analysis.get("target_points", 0),
                "stop_loss": analysis.get("stop_loss_points", 0),
            })
            logger.info(f"📊 Added {signal} signal to dashboard (confidence: {confidence}%)")
        else:
            # Log why we got NEUTRAL
            logger.info(f"⏸️ {index_name} NEUTRAL signal - {reasoning[:80]}...")
        
        # Send Telegram alert only if confidence meets threshold
        if signal in ["CALL", "PUT"] and confidence >= AI_CONFIG.min_confidence:
            logger.info(f"✅ Signal qualifies for alert: {signal} {confidence}% >= {AI_CONFIG.min_confidence}%")
            signal_key = f"{index_name}_{signal}_{analysis.get('entry_strike', 0)}"
            opposite_signal = "PUT" if signal == "CALL" else "CALL"
            
            # Check for flip-flop prevention (no opposite signal within 5 minutes)
            ist = pytz.timezone('Asia/Kolkata')
            current_time = datetime.now(ist)
            
            # Check if we sent an OPPOSITE signal recently (flip-flop prevention)
            flip_flop_threshold = 300  # 5 minutes
            flip_flop_blocked = False
            for key, last_time in self._last_signals.items():
                if key.startswith(f"{index_name}_{opposite_signal}_"):
                    time_since_opposite = (current_time - last_time).total_seconds()
                    if time_since_opposite < flip_flop_threshold:
                        logger.info(f"⏸️ Skipping {signal} - sent opposite signal {int(time_since_opposite)}s ago")
                        flip_flop_blocked = True
                        break
            
            if flip_flop_blocked:
                return
            
            # Track signal for performance analysis (even if alert is suppressed)
            tracker = get_signal_tracker()
            tracker.add_signal(
                index_name=index_name,
                signal_type=signal,
                strike=analysis.get("entry_strike", 0),
                entry_price=0,  # Will be updated when checking outcome
                spot_at_signal=spot_price,
                target_points=analysis.get("target_points", 0),
                stop_loss_points=analysis.get("stop_loss_points", 0),
                confidence=confidence,
                reasoning=reasoning,
            )
            
            # ALWAYS Open virtual trade for P&L tracking if confidence meets threshold
            virtual_trader = get_virtual_trader()
            entry_strike = analysis.get("entry_strike", 0)
            
            logger.info(f"🔥🔥🔥 ATTEMPTING TO OPEN VIRTUAL TRADE: {index_name} {signal} {entry_strike} 🔥🔥🔥")
            
            # Debug: Show current open trades
            open_trades = virtual_trader.get_open_trades()
            logger.info(f"📋 Current open trades: {len(open_trades)}")
            for t in open_trades:
                logger.info(f"   - {t.index} {t.signal_type} {t.strike}")
            
            # Prevent duplicate open trades for same strike/signal
            is_open = virtual_trader.is_position_open(index_name, signal, entry_strike)
            logger.info(f"🔍 is_position_open({index_name}, {signal}, {entry_strike}) = {is_open}")
            
            if is_open:
                logger.info(f"⏸️ Virtual position already open for {index_name} {signal} {entry_strike}")
            else:
                try:
                    # Try to fetch real entry premium from option chain
                    entry_premium = 100  # Default fallback
                    if strikes_data and entry_strike > 0:
                        for s in strikes_data:
                            if s.get('strike_price') == entry_strike:
                                entry_premium = s.get('call_lp' if signal == 'CALL' else 'put_lp', 100)
                                break
                    
                    logger.info(f"💰💰💰 OPENING VIRTUAL TRADE NOW: {signal} {index_name} {entry_strike} @ ₹{entry_premium} 💰💰💰")
                    
                    virtual_trader.open_trade(
                        index=index_name,
                        signal_type=signal,
                        strike=entry_strike,
                        spot_price=spot_price,
                        entry_premium=entry_premium,
                        target_points=analysis.get("target_points", 25),
                        stop_loss_points=analysis.get("stop_loss_points", 12),
                        reasoning=reasoning,
                        market_context={
                            "pcr": pcr,
                            "vwap": vwap,
                            "support": support,
                            "resistance": resistance
                        }
                    )
                    logger.info(f"✅✅✅ VIRTUAL TRADE OPENED SUCCESSFULLY! ✅✅✅")
                except Exception as vt_error:
                    logger.error(f"❌❌❌ ERROR OPENING VIRTUAL TRADE: {vt_error} ❌❌❌")
                    import traceback
                    logger.error(traceback.format_exc())

            # TELEGRAM ALERT NOTIFICATION LOGIC
            last_signal_time = self._last_signals.get(signal_key)
            time_threshold = 600  # 10 minutes in seconds
            
            should_send = (
                last_signal_time is None or 
                (current_time - last_signal_time).total_seconds() > time_threshold
            )
            
            if not should_send:
                time_since_last = (current_time - last_signal_time).total_seconds()
                logger.info(f"⏸️ Alert suppressed (repeat) - last sent {int(time_since_last)}s ago")
                return
            
            logger.info(f"📤 Sending Telegram alert for {index_name}...")
            
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
                index_name=index_display_name,
                trade_horizon=analysis.get("trade_horizon", "SCALP")
            )
            
            if alert_message:
                sent = await self.notifier.send_message(alert_message)
                if sent:
                    logger.info(f"📱 {index_name} Alert sent to Telegram")
                    self._last_signals[signal_key] = current_time
                    self.usage_monitor.current_usage.alerts_sent += 1
                else:
                    logger.error(f"❌ Failed to send Telegram alert for {index_name}")
        else:
            logger.info(f"⏸️ {index_name} No alert - Signal: {signal}, Confidence: {confidence}%")
        
        # Clear old signals periodically
        if len(self._last_signals) > 100:
            self._last_signals.clear()
    
    async def _update_virtual_trades(self):
        """Update virtual trades - check if target/SL hit."""
        try:
            virtual_trader = get_virtual_trader()
            enabled_indices = self.index_manager.get_enabled_indices()
            
            for index_config in enabled_indices:
                if index_config.name not in self._expiry_dates:
                    continue
                
                # Get current spot price
                spot_price = await self.data_fetcher.get_spot_price(index_config.symbol)
                if spot_price > 0:
                    closed_trades = virtual_trader.check_and_update_trades(index_config.name, spot_price)
                    
                    # Send telegram alerts for completed trades
                    for trade in closed_trades:
                        try:
                            exit_msg = virtual_trader.get_exit_message(trade)
                            await self.notifier.send_message(exit_msg)
                            logger.info(f"📱 Sent trade exit alert for {trade.index} {trade.signal_type}")
                        except Exception as e:
                            logger.error(f"Error sending trade exit alert: {e}")
        except Exception as e:
            logger.error(f"Error updating virtual trades: {e}")
    
    async def _send_hourly_showcase(self):
        """Send hourly performance showcase to Telegram."""
        try:
            virtual_trader = get_virtual_trader()
            
            if virtual_trader.should_send_hourly_update():
                showcase_msg = virtual_trader.get_showcase_message()
                await self.notifier.send_message(showcase_msg)
                logger.info("📊 Sent hourly performance showcase to Telegram")
        except Exception as e:
            logger.error(f"Error sending hourly showcase: {e}")
    
    async def _run_rule_based_analysis(self, index_name, spot_price, strikes_data, pcr_data, vwap):
        """Fallback to rule-based strategy."""
        logger.info("📊 Running rule-based analysis (AI fallback)")
        
        signals = self.strategy.analyze(
            spot_price=spot_price,
            strikes_data=strikes_data,
            pcr_data=pcr_data,
            vwap=vwap,
        )
        
        for signal in signals:
            if signal.confidence >= 0.4:
                reason = "\n".join(f"• {r}" for r in signal.reasons)
                signal_type_str = "CALL" if signal.signal_type == SignalType.CALL else "PUT"
                confidence_pct = int(signal.confidence * 100)
                
                # Add to dashboard for chart arrows
                add_signal({
                    "index": index_name,
                    "signal": signal_type_str,
                    "strike": signal.strike,
                    "confidence": confidence_pct,
                    "reasoning": f"[Rule-based] {reason[:80]}...",
                    "target": 25,
                    "stop_loss": 12,
                })
                logger.info(f"📊 Rule-based {signal_type_str} signal added to dashboard")
                
                # Send Telegram alert
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
                
                # Open virtual trade for P&L tracking
                virtual_trader = get_virtual_trader()
                if not virtual_trader.is_position_open(index_name, signal_type_str, signal.strike):
                    virtual_trader.open_trade(
                        index=index_name,
                        signal_type=signal_type_str,
                        strike=signal.strike,
                        spot_price=spot_price,
                        entry_premium=100,  # Default premium
                        target_points=25,
                        stop_loss_points=12,
                        reasoning=f"[Rule-based] {reason[:100]}",
                        market_context={"pcr": pcr_data.get('pcr_oi', 1.0), "vwap": vwap}
                    )
                    logger.info(f"📈 Rule-based virtual trade opened: {signal_type_str} {index_name} {signal.strike}")
                    
    async def _run_eod_analysis(self):
        """Analyze day's performance and generate learnings for tomorrow."""
        try:
            from performance_manager import get_performance_manager
            pm = get_performance_manager()
            virtual_trader = get_virtual_trader()
            
            ist = pytz.timezone('Asia/Kolkata')
            today_str = datetime.now(ist).strftime('%Y-%m-%d')
            
            # Get today's results
            stats = virtual_trader.get_stats()
            total_trades = stats.get('total_trades', 0)
            win_rate = stats.get('win_rate', 0)
            total_pnl = stats.get('total_pnl', 0)
            
            # Generate key learnings using AI
            if self.ai_analyzer and total_trades > 0:
                prompt = f"""Summarize today's trading performance and provide 2-3 specific "Key Learnings" for tomorrow.
                Data for {today_str}:
                - Total Trades: {total_trades}
                - Win Rate: {win_rate}%
                - Total P&L: ₹{total_pnl:,.0f}
                
                Respond in JSON format:
                {{
                    "market_summary": "Short 1-sentence summary of day's volatility",
                    "key_learnings": "1. Learning one... 2. Learning two..."
                }}
                """
                # Simple AI call for summary (using the same analyzer model)
                # We can reuse the _parse_ai_response or just calling directly
                session = await self.ai_analyzer._get_session()
                url = f"{self.ai_analyzer.base_url}/{self.ai_analyzer.model}:generateContent?key={self.ai_analyzer.api_key}"
                payload = {"contents": [{"parts": [{"text": prompt}]}]}
                
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        res = await resp.json()
                        text = res.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        analysis = self.ai_analyzer._parse_ai_response(text)
                        
                        pm.save_daily_analysis(today_str, {
                            'total_trades': total_trades,
                            'win_rate': win_rate,
                            'total_pnl': total_pnl,
                            'key_learnings': analysis.get('key_learnings', 'Keep following the strategy.'),
                            'market_summary': analysis.get('market_summary', 'Standard trading day.')
                        })
                        
                        logger.info(f"✅ EOD analysis saved with learnings: {analysis.get('key_learnings')}")
                        
                        # Notify on Telegram
                        eod_msg = f"🌅 <b>End-of-Day Analysis ({today_str})</b>\n\n"
                        eod_msg += f"📊 Total Trades: {total_trades}\n"
                        eod_msg += f"🏆 Win Rate: {win_rate}%\n"
                        eod_msg += f"💰 Realized P&L: ₹{total_pnl:,.0f}\n\n"
                        eod_msg += f"💡 <b>Key Learnings:</b>\n{analysis.get('key_learnings')}"
                        await self.notifier.send_message(eod_msg)
            
        except Exception as e:
            logger.error(f"Error in EOD analysis: {e}", exc_info=True)
    
    async def _fast_pnl_update_loop(self):
        """Ultra-fast loop to update P&L for dashboard (every 2 seconds)."""
        while self._running:
            try:
                if self.is_market_hours():
                    await self._update_virtual_trades()
                await asyncio.sleep(2)  # Update P&L every 2 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in fast P&L loop: {e}")
                await asyncio.sleep(5)

    async def run(self):
        """Main run loop."""
        if not await self.initialize():
            logger.error("❌ Failed to initialize trading system")
            return
        
        self._running = True
        logger.info(f"🔄 Starting main loop with {SYSTEM_CONFIG.refresh_interval_seconds}s interval")
        
        # Start fast P&L update loop
        asyncio.create_task(self._fast_pnl_update_loop())
        
        while self._running:
            try:
                if self.is_market_hours():
                    await self.run_ai_analysis_cycle()
                else:
                    ist = pytz.timezone('Asia/Kolkata')
                    now_ist = datetime.now(ist)
                    current_time = now_ist.strftime('%H:%M:%S')
                    current_date = now_ist.strftime('%Y-%m-%d')
                    
                    # Run EOD analysis once after market close
                    if self._eod_done_today != current_date and now_ist.hour >= 15:
                        logger.info("🌅 Market closed. Running End-of-Day analysis...")
                        await self._run_eod_analysis()
                        self._eod_done_today = current_date
                        
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
