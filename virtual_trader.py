"""
Virtual Trading Module for the F&O Trading System.
Tracks hypothetical trades based on AI signals and calculates P&L.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import pytz
from pathlib import Path

logger = logging.getLogger(__name__)

# Virtual trades file
VIRTUAL_TRADES_FILE = "virtual_trades.json"

# Lot sizes for different indices
LOT_SIZES = {
    "NIFTY": 65,
    "BANKNIFTY": 30,
    "FINNIFTY": 60,
    "MIDCPNIFTY": 120,
    "NIFTYNXT50": 25,
    "SENSEX": 10,
}

# Default option premium per point (approximate)
PREMIUM_PER_POINT = 1.0  # Will be adjusted based on moneyness


class VirtualTrade:
    """Represents a virtual/paper trade."""
    
    def __init__(self, data: Dict):
        self.id = data.get('id', 0)
        self.index = data.get('index', 'NIFTY')
        self.signal_type = data.get('signal_type', 'CALL')
        self.strike = data.get('strike', 0)
        self.spot_at_entry = data.get('spot_at_entry', 0)
        self.entry_premium = data.get('entry_premium', 100)  # Estimated option premium
        self.lot_size = data.get('lot_size', LOT_SIZES.get(self.index, 75))
        self.target_points = data.get('target_points', 30)
        self.stop_loss_points = data.get('stop_loss_points', 15)
        self.entry_time = data.get('entry_time', '')
        self.status = data.get('status', 'OPEN')  # OPEN, TARGET_HIT, SL_HIT, CLOSED
        self.exit_premium = data.get('exit_premium', None)
        self.exit_time = data.get('exit_time', None)
        self.points_captured = data.get('points_captured', 0)
        self.pnl = data.get('pnl', 0)
        self.highest_premium = data.get('highest_premium', self.entry_premium)
        self.lowest_premium = data.get('lowest_premium', self.entry_premium)
        self.current_premium = data.get('current_premium', self.entry_premium)
        self.current_pnl = data.get('current_pnl', 0)
        self.reasoning = data.get('reasoning', '')
        self.market_context = data.get('market_context', {})
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'index': self.index,
            'signal_type': self.signal_type,
            'strike': self.strike,
            'spot_at_entry': self.spot_at_entry,
            'entry_premium': self.entry_premium,
            'current_premium': self.current_premium,
            'lot_size': self.lot_size,
            'lot_count': getattr(self, 'lot_count', 10),
            'base_lot_size': getattr(self, 'base_lot_size', self.lot_size / 10 if self.lot_size else 65),
            'target_points': self.target_points,
            'stop_loss_points': self.stop_loss_points,
            'entry_time': self.entry_time,
            'status': self.status,
            'exit_premium': self.exit_premium,
            'exit_time': self.exit_time,
            'points_captured': self.points_captured,
            'pnl': self.pnl,
            'current_pnl': self.current_pnl,
            'current_points': self.current_premium - self.entry_premium,
            'required_capital': self.entry_premium * self.lot_size,
            'roi_percentage': ((self.current_pnl / (self.entry_premium * self.lot_size)) * 100) if self.entry_premium > 0 else 0,
            'highest_premium': self.highest_premium,
            'lowest_premium': self.lowest_premium,
            'reasoning': self.reasoning,
            'market_context': self.market_context,
        }
    
    def calculate_pnl(self, current_premium: float) -> float:
        """Calculate P&L based on current premium."""
        points = current_premium - self.entry_premium
        return points * self.lot_size
    
    def update_mtm(self, current_premium: float):
        """Update mark-to-market values."""
        self.current_premium = current_premium
        self.current_pnl = (current_premium - self.entry_premium) * self.lot_size
        
        if current_premium > self.highest_premium:
            self.highest_premium = current_premium
        if current_premium < self.lowest_premium:
            self.lowest_premium = current_premium


class VirtualTrader:
    """Manages virtual/paper trades for performance showcase."""
    
    def __init__(self):
        self.trades: List[VirtualTrade] = []
        self.total_pnl = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.last_hourly_update = None
        self.load()
    
    def load(self):
        """Load trades from file."""
        try:
            if Path(VIRTUAL_TRADES_FILE).exists():
                with open(VIRTUAL_TRADES_FILE, 'r') as f:
                    data = json.load(f)
                    self.trades = [VirtualTrade(t) for t in data.get('trades', [])]
                    self.total_pnl = data.get('total_pnl', 0)
                    self.winning_trades = data.get('winning_trades', 0)
                    self.losing_trades = data.get('losing_trades', 0)
                logger.info(f"Loaded {len(self.trades)} virtual trades")
        except Exception as e:
            logger.error(f"Error loading virtual trades: {e}")
    
    def save(self):
        """Save trades to file."""
        try:
            data = {
                'trades': [t.to_dict() for t in self.trades],
                'total_pnl': self.total_pnl,
                'winning_trades': self.winning_trades,
                'losing_trades': self.losing_trades,
            }
            with open(VIRTUAL_TRADES_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving virtual trades: {e}")
    
    def open_trade(
        self,
        index: str,
        signal_type: str,
        strike: int,
        spot_price: float,
        entry_premium: float,
        target_points: int,
        stop_loss_points: int,
        reasoning: str = '',
        market_context: Dict = None,
    ) -> VirtualTrade:
        """Open a new virtual trade."""
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        
        # Get lot size for index
        index_key = index.upper().replace(" ", "").replace("50", "").replace("BANK", "BANKNIFTY")
        if "BANK" in index.upper():
            index_key = "BANKNIFTY"
        elif "NIFTY" in index.upper():
            index_key = "NIFTY"
        elif "SENSEX" in index.upper():
            index_key = "SENSEX"
        
        # Default to 10 lots per trade as requested
        base_lot_size = LOT_SIZES.get(index_key, 65)
        lot_count = 10
        lot_size = base_lot_size * lot_count
        
        trade = VirtualTrade({
            'id': len(self.trades) + 1,
            'index': index,
            'signal_type': signal_type,
            'strike': strike,
            'spot_at_entry': spot_price,
            'entry_premium': entry_premium,
            'lot_size': lot_size,
            'lot_count': lot_count,
            'base_lot_size': base_lot_size,
            'target_points': target_points,
            'stop_loss_points': stop_loss_points,
            'entry_time': now.strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'OPEN',
            'reasoning': reasoning,
            'market_context': market_context or {},
        })
        
        self.trades.append(trade)
        self.save()
        
        logger.info(f"📈 Virtual Trade #{trade.id} opened: {signal_type} {index} {strike} @ ₹{entry_premium}")
        return trade
    
    def close_trade(self, trade_id: int, exit_premium: float, status: str = 'CLOSED'):
        """Close a virtual trade."""
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        
        for trade in self.trades:
            if trade.id == trade_id and trade.status == 'OPEN':
                trade.exit_premium = exit_premium
                trade.exit_time = now.strftime('%Y-%m-%d %H:%M:%S')
                trade.status = status
                trade.points_captured = exit_premium - trade.entry_premium
                trade.pnl = trade.points_captured * trade.lot_size
                
                self.total_pnl += trade.pnl
                if trade.pnl > 0:
                    self.winning_trades += 1
                else:
                    self.losing_trades += 1
                
                self.save()
                
                # Log to permanent database
                try:
                    from performance_manager import get_performance_manager
                    get_performance_manager().log_trade(trade.to_dict())
                except Exception as db_err:
                    logger.error(f"Failed to log trade to permanent DB: {db_err}")
                    
                logger.info(f"📊 Virtual Trade #{trade_id} closed: {status} | P&L: ₹{trade.pnl:,.0f}")
                return trade
        return None
    
    def check_and_update_trades(self, index: str, spot_price: float, option_prices: Dict[int, Dict] = None) -> List[VirtualTrade]:
        """Check open trades and update their status based on current prices."""
        closed_trades = []
        for trade in self.trades:
            if trade.status != 'OPEN':
                continue
            if trade.index != index:
                continue
            
            # Estimate current premium based on spot movement
            spot_change = spot_price - trade.spot_at_entry
            
            # For CALL: premium increases when spot goes up
            # For PUT: premium increases when spot goes down
            if trade.signal_type == 'CALL':
                premium_change = spot_change * 0.5  # Delta ~0.5 for ATM
            else:
                premium_change = -spot_change * 0.5
            
            current_premium = max(1, trade.entry_premium + premium_change)
            trade.update_mtm(current_premium)
            
            # Check target hit
            if current_premium >= trade.entry_premium + trade.target_points:
                closed = self.close_trade(trade.id, trade.entry_premium + trade.target_points, 'TARGET_HIT')
                if closed: closed_trades.append(closed)
            # Check stop loss hit
            elif current_premium <= trade.entry_premium - trade.stop_loss_points:
                closed = self.close_trade(trade.id, trade.entry_premium - trade.stop_loss_points, 'SL_HIT')
                if closed: closed_trades.append(closed)
        
        self.save()
        return closed_trades
    
    def get_open_trades(self) -> List[VirtualTrade]:
        """Get all open trades."""
        return [t for t in self.trades if t.status == 'OPEN']
    
    def is_position_open(self, index: str, signal_type: str, strike: int) -> bool:
        """Check if a specific position is already open."""
        for t in self.get_open_trades():
            if t.index == index and t.signal_type == signal_type and t.strike == strike:
                return True
        return False
    
    def get_todays_trades(self) -> List[VirtualTrade]:
        """Get today's trades."""
        ist = pytz.timezone('Asia/Kolkata')
        today = datetime.now(ist).strftime('%Y-%m-%d')
        return [t for t in self.trades if t.entry_time.startswith(today)]
    
    def get_stats(self) -> Dict:
        """Get trading statistics."""
        todays_trades = self.get_todays_trades()
        todays_pnl = sum(t.pnl for t in todays_trades if t.status != 'OPEN')
        
        total_trades = self.winning_trades + self.losing_trades
        win_rate = (self.winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        return {
            'total_trades': len(self.trades),
            'open_trades': len(self.get_open_trades()),
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': round(win_rate, 1),
            'total_pnl': round(self.total_pnl, 0),
            'todays_trades': len(todays_trades),
            'todays_pnl': round(todays_pnl, 0),
        }
    
    def get_showcase_message(self) -> str:
        """Generate a showcase message for Telegram."""
        stats = self.get_stats()
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        
        # Get recent closed trades
        recent_trades = [t for t in self.trades if t.status != 'OPEN'][-5:]
        
        trades_list = ""
        for t in recent_trades[::-1]:
            emoji = "✅" if t.pnl > 0 else "❌"
            trades_list += f"{emoji} {t.signal_type} {t.index} {t.strike}: ₹{t.pnl:+,.0f}\n"
        
        pnl_emoji = "🟢" if stats['total_pnl'] >= 0 else "🔴"
        today_emoji = "📈" if stats['todays_pnl'] >= 0 else "📉"
        
        message = f"""
💰 <b>AI TRADING PERFORMANCE SHOWCASE</b> 💰
━━━━━━━━━━━━━━━━━━━━━━━━━━━

{pnl_emoji} <b>Total P&L: ₹{stats['total_pnl']:+,.0f}</b>
{today_emoji} <b>Today's P&L: ₹{stats['todays_pnl']:+,.0f}</b>

📊 <b>STATISTICS:</b>
• Total Trades: {stats['total_trades']}
• Win Rate: {stats['win_rate']}%
• Winning: {stats['winning_trades']} | Losing: {stats['losing_trades']}
• Open Positions: {stats['open_trades']}

📋 <b>RECENT TRADES:</b>
{trades_list if trades_list else "No closed trades yet"}
━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ {now.strftime('%H:%M:%S')} | {now.strftime('%d-%b-%Y')}

<i>*Virtual trading based on AI signals. 
Not actual trades. 1 lot per signal.</i>
"""
        return message

    def get_exit_message(self, trade: VirtualTrade) -> str:
        """Generate a detailed message for a trade exit."""
        emoji = "✅" if trade.pnl > 0 else "❌"
        status_text = "TARGET ACHIEVED 🎯" if trade.status == 'TARGET_HIT' else "STOP LOSS HIT 🛑"
        if trade.status == 'MANUAL_EXIT':
            status_text = "MANUAL EXIT 🚪"
        pnl_color = "🟢" if trade.pnl > 0 else "🔴"
        required_cap = trade.entry_premium * trade.lot_size
        roi = (trade.pnl / required_cap * 100) if required_cap > 0 else 0
        
        return f"""
{emoji} <b>VIRTUAL TRADE EXIT: {status_text}</b> {emoji}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 <b>Trade Details:</b>
• Index: {trade.index}
• Signal: {trade.signal_type}
• Strike: {trade.strike}
• Lot Size: {trade.lot_size}
• Capital Used: ₹{required_cap:,.2f}

💰 <b>Performance:</b>
• Entry Price: ₹{trade.entry_premium}
• Exit Price: ₹{trade.exit_premium}
• Points: {trade.points_captured:+.1f}
• ROI: {roi:+.2f}%
• {pnl_color} <b>Final P&L: ₹{trade.pnl:+,.0f}</b>

⏰ Entry: {trade.entry_time}
⏰ Exit: {trade.exit_time}
━━━━━━━━━━━━━━━━━━━━━━━━━━━
<i>*Virtual trading analysis. No actual funds used.</i>
"""
    
    def should_send_hourly_update(self) -> bool:
        """Check if hourly update should be sent."""
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        
        # Only send during market hours
        if now.hour < 9 or now.hour > 15:
            return False
        
        # Check if an hour has passed since last update
        if self.last_hourly_update is None:
            self.last_hourly_update = now
            return True
        
        if (now - self.last_hourly_update).total_seconds() >= 3600:
            self.last_hourly_update = now
            return True
        
        return False


# Global instance
_virtual_trader = None


def get_virtual_trader() -> VirtualTrader:
    """Get or create the global virtual trader."""
    global _virtual_trader
    if _virtual_trader is None:
        _virtual_trader = VirtualTrader()
    return _virtual_trader
