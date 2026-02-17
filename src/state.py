"""
State persistence for Icaro Trading Bot.
Saves and loads bot state to survive restarts.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict

from src.config import get_config


@dataclass
class BotState:
    """Represents the current state of the trading bot."""
    
    # Trading state
    starting_capital: float = 10.0
    current_capital: float = 0.0
    total_profit_usdc: float = 0.0
    total_profit_percent: float = 0.0
    
    # Statistics
    total_trades: int = 0
    successful_buys: int = 0
    successful_sells: int = 0
    failed_trades: int = 0
    
    # Performance
    best_trade_profit: float = 0.0
    best_trade_symbol: str = ""
    worst_trade_loss: float = 0.0
    worst_trade_symbol: str = ""
    
    # Tracking
    positions: Dict[str, Dict] = field(default_factory=dict)  # symbol -> {quantity, avg_price, entry_time}
    recent_decisions: List[Dict] = field(default_factory=list)
    
    # Timestamps
    started_at: str = ""
    last_updated: str = ""
    last_trade_at: str = ""
    
    # Session info
    total_runtime_seconds: int = 0
    decision_cycles: int = 0


class StateManager:
    """Manages bot state persistence."""
    
    def __init__(self):
        self.config = get_config()
        self.state_path = self.config.data_dir / "bot_state.json"
        self.state: BotState = BotState()
        self._load()
    
    def _load(self) -> None:
        """Load state from file."""
        if self.state_path.exists():
            try:
                with open(self.state_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Update state with loaded data
                for key, value in data.items():
                    if hasattr(self.state, key):
                        setattr(self.state, key, value)
                
                print(f"✓ Loaded previous state (trades: {self.state.total_trades}, cycles: {self.state.decision_cycles})")
            except Exception as e:
                print(f"⚠️ Could not load state: {e}")
        else:
            # First run
            self.state.started_at = datetime.now().isoformat()
            self._save()
    
    def _save(self) -> None:
        """Save state to file."""
        self.state.last_updated = datetime.now().isoformat()
        
        try:
            with open(self.state_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(self.state), f, indent=2, default=str)
        except Exception as e:
            print(f"⚠️ Could not save state: {e}")
    
    def update_portfolio(self, portfolio: Dict) -> None:
        """Update current capital from portfolio."""
        self.state.current_capital = portfolio.get('total_value_usdc', 0)
        
        if self.state.starting_capital > 0:
            self.state.total_profit_usdc = self.state.current_capital - self.state.starting_capital
            self.state.total_profit_percent = (self.state.total_profit_usdc / self.state.starting_capital) * 100
        
        self._save()
    
    def record_trade(self, trade: Dict) -> None:
        """Record a completed trade."""
        if not trade.get('success'):
            self.state.failed_trades += 1
            self._save()
            return
        
        self.state.total_trades += 1
        self.state.last_trade_at = datetime.now().isoformat()
        
        side = trade.get('side', '')
        symbol = trade.get('symbol', '')
        quantity = trade.get('quantity', 0)
        price = trade.get('price', 0)
        total = trade.get('total_usdc', 0)
        
        if side == 'BUY':
            self.state.successful_buys += 1
            
            # Track position
            if symbol not in self.state.positions:
                self.state.positions[symbol] = {
                    'quantity': 0,
                    'total_cost': 0,
                    'entry_time': datetime.now().isoformat()
                }
            
            pos = self.state.positions[symbol]
            pos['quantity'] += quantity
            pos['total_cost'] += total
            pos['avg_price'] = pos['total_cost'] / pos['quantity'] if pos['quantity'] > 0 else 0
            
        elif side == 'SELL':
            self.state.successful_sells += 1
            
            # Calculate profit if we have position data
            if symbol in self.state.positions:
                pos = self.state.positions[symbol]
                avg_buy_price = pos.get('avg_price', 0)
                
                if avg_buy_price > 0:
                    cost_basis = quantity * avg_buy_price
                    profit = total - cost_basis
                    
                    # Track best/worst trades
                    if profit > self.state.best_trade_profit:
                        self.state.best_trade_profit = profit
                        self.state.best_trade_symbol = symbol
                    
                    if profit < self.state.worst_trade_loss:
                        self.state.worst_trade_loss = profit
                        self.state.worst_trade_symbol = symbol
                
                # Update position
                pos['quantity'] -= quantity
                if pos['quantity'] <= 0:
                    del self.state.positions[symbol]
                else:
                    pos['total_cost'] = pos['quantity'] * pos['avg_price']
        
        self._save()
    
    def record_decision(self, decision: Dict) -> None:
        """Record a decision cycle."""
        self.state.decision_cycles += 1
        
        summary = {
            'timestamp': datetime.now().isoformat(),
            'actions': len(decision.get('actions', [])),
            'response_preview': (decision.get('response', '') or '')[:100]
        }
        
        self.state.recent_decisions.append(summary)
        
        # Keep only last 20 decisions
        if len(self.state.recent_decisions) > 20:
            self.state.recent_decisions = self.state.recent_decisions[-20:]
        
        self._save()
    
    def add_runtime(self, seconds: int) -> None:
        """Add to total runtime."""
        self.state.total_runtime_seconds += seconds
        self._save()
    
    def get_summary(self) -> Dict:
        """Get a summary of the current state."""
        return {
            'started_at': self.state.started_at,
            'runtime_hours': round(self.state.total_runtime_seconds / 3600, 2),
            'decision_cycles': self.state.decision_cycles,
            'total_trades': self.state.total_trades,
            'current_capital': self.state.current_capital,
            'profit_usdc': round(self.state.total_profit_usdc, 2),
            'profit_percent': round(self.state.total_profit_percent, 2),
            'active_positions': len(self.state.positions),
            'best_trade': f"{self.state.best_trade_symbol} (+${self.state.best_trade_profit:.2f})" if self.state.best_trade_symbol else "N/A",
            'worst_trade': f"{self.state.worst_trade_symbol} (${self.state.worst_trade_loss:.2f})" if self.state.worst_trade_symbol else "N/A"
        }
    
    def reset(self) -> None:
        """Reset state (use with caution)."""
        self.state = BotState()
        self.state.started_at = datetime.now().isoformat()
        self._save()


# Singleton instance
_state_manager: Optional[StateManager] = None

def get_state_manager() -> StateManager:
    """Get the global state manager instance."""
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager
