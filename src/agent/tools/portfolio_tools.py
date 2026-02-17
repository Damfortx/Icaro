"""
Portfolio Analysis Tools for the DeepSeek Agent.
Provides functions for tracking and analyzing portfolio performance.
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

from src.config import get_config
from src.agent.system_prompt import get_prompt_manager


async def calculate_performance() -> Dict[str, Any]:
    """
    Calculate overall trading performance from trade history.
    
    Returns:
        Performance metrics including total trades, win rate, best trade, P&L
    """
    config = get_config()
    history_path = config.data_dir / "trade_history.json"
    
    try:
        with open(history_path, 'r') as f:
            trades = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        trades = []
    
    if not trades:
        return {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0.0,
            'total_profit_usdc': 0.0,
            'best_trade': None,
            'worst_trade': None,
            'current_pnl_percent': 0.0
        }
    
    # Analyze trades
    total_trades = len(trades)
    buys = [t for t in trades if t.get('side') == 'BUY' and t.get('success')]
    sells = [t for t in trades if t.get('side') == 'SELL' and t.get('success')]
    
    # Simple P&L calculation (buy cost vs sell revenue)
    total_bought = sum(t.get('total_usdc', 0) for t in buys)
    total_sold = sum(t.get('total_usdc', 0) for t in sells)
    
    profit = total_sold - total_bought
    pnl_percent = (profit / total_bought * 100) if total_bought > 0 else 0
    
    # Track winning trades (sells at profit)
    # This is simplified - real implementation would track buy price per position
    wins = len([t for t in sells if t.get('success')])
    
    return {
        'total_trades': total_trades,
        'successful_buys': len(buys),
        'successful_sells': len(sells),
        'total_bought_usdc': round(total_bought, 2),
        'total_sold_usdc': round(total_sold, 2),
        'profit_usdc': round(profit, 2),
        'pnl_percent': round(pnl_percent, 2)
    }


async def update_strategy(learning: str, adjustment: str) -> Dict[str, Any]:
    """
    Record a learning and strategy adjustment.
    Updates both the system prompt and learnings file.
    
    Args:
        learning: What was learned from recent trading
        adjustment: How the strategy should be adjusted
    
    Returns:
        Confirmation of the update
    """
    config = get_config()
    
    # Update system prompt
    prompt_manager = get_prompt_manager()
    prompt_manager.append_learning(learning, adjustment)
    
    # Also save to learnings.json for structured data
    learnings_path = config.data_dir / "learnings.json"
    
    try:
        with open(learnings_path, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"learnings": [], "strategy_adjustments": [], "performance_notes": []}
    
    timestamp = datetime.now().isoformat()
    
    data['learnings'].append({
        'timestamp': timestamp,
        'learning': learning
    })
    
    data['strategy_adjustments'].append({
        'timestamp': timestamp,
        'adjustment': adjustment
    })
    
    with open(learnings_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    return {
        'success': True,
        'message': 'Strategy updated successfully',
        'learning': learning,
        'adjustment': adjustment,
        'timestamp': timestamp
    }


async def log_decision(decision: str, outcome: str) -> None:
    """Log a trading decision to the system prompt."""
    prompt_manager = get_prompt_manager()
    prompt_manager.add_recent_decision(decision, outcome)


async def get_learnings() -> List[Dict]:
    """Get all recorded learnings."""
    config = get_config()
    learnings_path = config.data_dir / "learnings.json"
    
    try:
        with open(learnings_path, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"learnings": []}
    
    return data.get('learnings', [])


# Tool definitions for DeepSeek function calling
PORTFOLIO_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "calculate_performance",
            "description": "Calculate overall trading performance including total trades, profit/loss, and win rate. Use this to evaluate your strategy.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_strategy",
            "description": "Record a learning from your trading experience and how you'll adjust your strategy. This updates your system prompt for future decisions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "learning": {
                        "type": "string",
                        "description": "What you learned from recent trading (e.g., 'High volume coins tend to have more stable moves')"
                    },
                    "adjustment": {
                        "type": "string",
                        "description": "How you'll adjust your strategy (e.g., 'Focus on coins with >$1M 24h volume')"
                    }
                },
                "required": ["learning", "adjustment"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_learnings",
            "description": "Retrieve all your recorded learnings to review past insights and strategy adjustments.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]
