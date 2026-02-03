"""
Multi-Index Configuration for F&O Trading System.
Defines supported indices and their properties.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import json
import os

@dataclass
class IndexConfig:
    """Configuration for a trading index."""
    name: str
    display_name: str
    symbol: str
    exchange: str
    enabled: bool = True
    option_symbol_prefix: str = ""
    lot_size: int = 1
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "enabled": self.enabled,
            "option_symbol_prefix": self.option_symbol_prefix,
            "lot_size": self.lot_size,
        }


# Available indices configurations
AVAILABLE_INDICES: Dict[str, IndexConfig] = {
    "NIFTY": IndexConfig(
        name="NIFTY",
        display_name="NIFTY 50",
        symbol="NSE_INDEX|Nifty 50",
        exchange="NSE",
        enabled=True,
        option_symbol_prefix="NIFTY",
        lot_size=75,
    ),
    "BANKNIFTY": IndexConfig(
        name="BANKNIFTY",
        display_name="Bank NIFTY",
        symbol="NSE_INDEX|Nifty Bank",
        exchange="NSE",
        enabled=True,
        option_symbol_prefix="BANKNIFTY",
        lot_size=30,
    ),
    "SENSEX": IndexConfig(
        name="SENSEX",
        display_name="BSE SENSEX",
        symbol="BSE_INDEX|SENSEX",
        exchange="BSE",
        enabled=True,
        option_symbol_prefix="SENSEX",
        lot_size=10,
    ),
    "FINNIFTY": IndexConfig(
        name="FINNIFTY",
        display_name="Fin NIFTY",
        symbol="NSE_INDEX|Nifty Fin Service",
        exchange="NSE",
        enabled=False,  # Disabled by default
        option_symbol_prefix="FINNIFTY",
        lot_size=40,
    ),
    "MIDCPNIFTY": IndexConfig(
        name="MIDCPNIFTY",
        display_name="Midcap NIFTY",
        symbol="NSE_INDEX|NIFTY MID SELECT",
        exchange="NSE",
        enabled=False,  # Disabled by default
        option_symbol_prefix="MIDCPNIFTY",
        lot_size=75,
    ),
}


class IndexManager:
    """Manages index configurations with persistence."""
    
    CONFIG_FILE = "index_config.json"
    
    def __init__(self):
        self.indices: Dict[str, IndexConfig] = {}
        self._load_config()
    
    def _load_config(self):
        """Load index configuration from file or use defaults."""
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, 'r') as f:
                    saved_config = json.load(f)
                    
                # Merge saved config with available indices
                for name, config in AVAILABLE_INDICES.items():
                    self.indices[name] = IndexConfig(**config.to_dict())
                    if name in saved_config.get("enabled_indices", []):
                        self.indices[name].enabled = True
                    elif name in saved_config.get("disabled_indices", []):
                        self.indices[name].enabled = False
            except Exception as e:
                print(f"Error loading index config: {e}")
                self._use_defaults()
        else:
            self._use_defaults()
    
    def _use_defaults(self):
        """Use default configuration."""
        self.indices = {
            name: IndexConfig(**config.to_dict()) 
            for name, config in AVAILABLE_INDICES.items()
        }
    
    def save_config(self):
        """Save current configuration to file."""
        config = {
            "enabled_indices": [
                name for name, idx in self.indices.items() if idx.enabled
            ],
            "disabled_indices": [
                name for name, idx in self.indices.items() if not idx.enabled
            ],
        }
        try:
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving index config: {e}")
    
    def get_enabled_indices(self) -> List[IndexConfig]:
        """Get list of enabled indices."""
        return [idx for idx in self.indices.values() if idx.enabled]
    
    def get_all_indices(self) -> List[IndexConfig]:
        """Get all indices."""
        return list(self.indices.values())
    
    def toggle_index(self, name: str) -> bool:
        """Toggle an index on/off. Returns new state."""
        if name in self.indices:
            self.indices[name].enabled = not self.indices[name].enabled
            self.save_config()
            return self.indices[name].enabled
        return False
    
    def enable_index(self, name: str):
        """Enable an index."""
        if name in self.indices:
            self.indices[name].enabled = True
            self.save_config()
    
    def disable_index(self, name: str):
        """Disable an index."""
        if name in self.indices:
            self.indices[name].enabled = False
            self.save_config()
    
    def get_index(self, name: str) -> Optional[IndexConfig]:
        """Get a specific index configuration."""
        return self.indices.get(name)
    
    def get_status(self) -> Dict[str, bool]:
        """Get enabled/disabled status of all indices."""
        return {name: idx.enabled for name, idx in self.indices.items()}


# Global index manager instance
index_manager = IndexManager()


def get_index_manager() -> IndexManager:
    """Get the global index manager instance."""
    return index_manager
