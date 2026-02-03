"""
Signal Tracker Module for the F&O Trading System.
Tracks signal performance and calculates success rates.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Optional, List
import pytz
from pathlib import Path

logger = logging.getLogger(__name__)

# Signal tracking file
SIGNALS_FILE = "signal_history.json"


class SignalTracker:
    """Tracks signals and their outcomes for performance analysis."""
    
    def __init__(self):
        self.signals: List[Dict] = []
        self.load()
    
    def load(self):
        """Load signals from file."""
        try:
            if Path(SIGNALS_FILE).exists():
                with open(SIGNALS_FILE, 'r') as f:
                    self.signals = json.load(f)
                logger.info(f"Loaded {len(self.signals)} historical signals")
        except Exception as e:
            logger.error(f"Error loading signals: {e}")
            self.signals = []
    
    def save(self):
        """Save signals to file."""
        try:
            with open(SIGNALS_FILE, 'w') as f:
                json.dump(self.signals, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving signals: {e}")
    
    def add_signal(
        self,
        index_name: str,
        signal_type: str,  # CALL or PUT
        strike: int,
        entry_price: float,
        spot_at_signal: float,
        target_points: int,
        stop_loss_points: int,
        confidence: int,
        reasoning: str,
    ):
        """Add a new signal to track."""
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        
        signal = {
            "id": len(self.signals) + 1,
            "index": index_name,
            "type": signal_type,
            "strike": strike,
            "entry_price": entry_price,
            "spot_at_signal": spot_at_signal,
            "target_points": target_points,
            "stop_loss_points": stop_loss_points,
            "confidence": confidence,
            "reasoning": reasoning[:200],
            "timestamp": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "outcome": None,  # Will be updated: "TARGET_HIT", "SL_HIT", "EXPIRED"
            "exit_price": None,
            "points_gained": None,
            "closed_at": None,
        }
        
        self.signals.append(signal)
        self.save()
        logger.info(f"📊 Signal #{signal['id']} tracked: {signal_type} @ {strike}")
        return signal['id']
    
    def update_signal_outcome(
        self,
        signal_id: int,
        outcome: str,
        exit_price: float,
        points_gained: float,
    ):
        """Update signal with its outcome."""
        for signal in self.signals:
            if signal['id'] == signal_id:
                ist = pytz.timezone('Asia/Kolkata')
                signal['outcome'] = outcome
                signal['exit_price'] = exit_price
                signal['points_gained'] = points_gained
                signal['closed_at'] = datetime.now(ist).isoformat()
                self.save()
                logger.info(f"📊 Signal #{signal_id} closed: {outcome} ({points_gained:+.0f} pts)")
                return True
        return False
    
    def get_stats(self, index_name: Optional[str] = None, days: int = 7) -> Dict:
        """Get performance statistics."""
        ist = pytz.timezone('Asia/Kolkata')
        cutoff = datetime.now(ist).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Filter signals
        filtered = self.signals
        if index_name:
            filtered = [s for s in filtered if s['index'] == index_name]
        
        # Calculate stats
        total = len(filtered)
        closed = [s for s in filtered if s['outcome'] is not None]
        
        target_hit = len([s for s in closed if s['outcome'] == 'TARGET_HIT'])
        sl_hit = len([s for s in closed if s['outcome'] == 'SL_HIT'])
        expired = len([s for s in closed if s['outcome'] == 'EXPIRED'])
        
        total_points = sum(s.get('points_gained', 0) or 0 for s in closed)
        
        success_rate = (target_hit / len(closed) * 100) if closed else 0
        
        return {
            "total_signals": total,
            "closed_signals": len(closed),
            "open_signals": total - len(closed),
            "target_hit": target_hit,
            "sl_hit": sl_hit,
            "expired": expired,
            "success_rate": round(success_rate, 1),
            "total_points": round(total_points, 1),
            "avg_points": round(total_points / len(closed), 1) if closed else 0,
        }
    
    def get_summary_message(self, index_name: Optional[str] = None) -> str:
        """Generate a performance summary message."""
        stats = self.get_stats(index_name)
        
        index_str = f" ({index_name})" if index_name else ""
        
        return f"""
📊 <b>Signal Performance{index_str}</b>

✅ Success Rate: <b>{stats['success_rate']}%</b>

📈 Total Signals: {stats['total_signals']}
🎯 Target Hit: {stats['target_hit']}
🛑 Stop Loss Hit: {stats['sl_hit']}
⏱️ Expired: {stats['expired']}
📊 Open: {stats['open_signals']}

💰 Total Points: {stats['total_points']:+.0f}
📉 Avg Points/Trade: {stats['avg_points']:+.0f}
"""
    
    def get_open_signals(self) -> List[Dict]:
        """Get all signals that haven't been closed yet."""
        return [s for s in self.signals if s['outcome'] is None]


# Global tracker instance
_tracker = None


def get_signal_tracker() -> SignalTracker:
    """Get or create the global signal tracker."""
    global _tracker
    if _tracker is None:
        _tracker = SignalTracker()
    return _tracker
