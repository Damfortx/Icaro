"""
Binance Trading Tools for the DeepSeek Agent.
Provides functions for portfolio management and trading operations.
"""

import json
from typing import Dict, List, Any
from datetime import datetime
from pathlib import Path

from src.config import get_config
from src.exchange.binance_client import get_binance_client


async def get_portfolio() -> Dict[str, Any]:
    """
    Get current portfolio holdings and total value.
    
    Returns:
        Dictionary with holdings, USDC balance, and total portfolio value
    """
    client = await get_binance_client()
    balances = await client.get_account_balance()
    
    # Calculate total value in USDC
    usdc_balance = balances.get('USDC', {}).get('free', 0)
    holdings = []
    total_value = usdc_balance
    
    # Get prices for holdings
    prices = await client.get_all_tickers()
    quote = get_config().trading.quote_currency
    
    for asset, balance_info in balances.items():
        if asset == quote:
            continue
            
        symbol = f"{asset}{quote}"
        price = prices.get(symbol, 0)
        value = balance_info['total'] * price
        
        if value > 0.01:  # Only include if worth more than 1 cent
            holdings.append({
                'asset': asset,
                'quantity': balance_info['total'],
                'price': price,
                'value_usdc': round(value, 2),
                'free': balance_info['free'],
                'locked': balance_info['locked']
            })
            total_value += value
    
    return {
        'usdc_available': round(usdc_balance, 2),
        'holdings': holdings,
        'total_value_usdc': round(total_value, 2),
        'num_positions': len(holdings),
        'timestamp': datetime.now().isoformat()
    }


async def get_top_gainers(limit: int = 10) -> List[Dict]:
    """
    Get top gaining coins in the last 24 hours.
    
    Args:
        limit: Number of top gainers to return
    
    Returns:
        List of top gaining coins with stats
    """
    client = await get_binance_client()
    gainers = await client.get_top_gainers(limit)
    
    # Add additional context
    for g in gainers:
        if g['volume'] > 1_000_000:
            g['volume_tier'] = 'high'
        elif g['volume'] > 100_000:
            g['volume_tier'] = 'medium'
        else:
            g['volume_tier'] = 'low'
    
    return gainers


async def get_coin_stats(symbol: str) -> Dict:
    """
    Get detailed statistics for a specific coin.
    
    Args:
        symbol: The coin symbol (e.g., 'BTC' or 'BTCUSDC')
    
    Returns:
        Detailed 24h statistics for the coin
    """
    client = await get_binance_client()
    quote = get_config().trading.quote_currency
    
    # Ensure we have the full trading pair
    if not symbol.endswith(quote):
        symbol = f"{symbol}{quote}"
    
    stats = await client.get_24h_stats(symbol)
    
    # Add helpful interpretations
    change = stats['priceChangePercent']
    if change > 10:
        stats['momentum'] = 'strong_bullish'
    elif change > 3:
        stats['momentum'] = 'bullish'
    elif change > -3:
        stats['momentum'] = 'neutral'
    elif change > -10:
        stats['momentum'] = 'bearish'
    else:
        stats['momentum'] = 'strong_bearish'
    
    return stats


async def buy_coin(symbol: str, amount_usdc: float, reason: str) -> Dict:
    """
    Buy a coin with USDC.
    
    Args:
        symbol: Coin to buy (e.g., 'BTC' or 'BTCUSDC')
        amount_usdc: Amount of USDC to spend
        reason: Reason for the trade
    
    Returns:
        Trade result
    """
    client = await get_binance_client()
    config = get_config()
    quote = config.trading.quote_currency
    
    # Ensure we have the full trading pair
    if not symbol.upper().endswith(quote):
        symbol = f"{symbol.upper()}{quote}"
    
    # Validate against config limits
    usdc_balance = await client.get_usdc_balance()
    available = usdc_balance - config.trading.reserve_usdc
    
    if amount_usdc > available:
        return {
            'success': False,
            'error': f'Insufficient funds. Available: {available:.2f} USDC (keeping {config.trading.reserve_usdc} reserve)',
            'requested': amount_usdc
        }
    
    if amount_usdc < config.trading.min_trade_usdc:
        return {
            'success': False,
            'error': f'Amount below minimum trade size of {config.trading.min_trade_usdc} USDC',
            'requested': amount_usdc
        }
    
    # Check max position rule
    portfolio = await get_portfolio()
    max_position = portfolio['total_value_usdc'] * (config.trading.max_position_percent / 100)
    
    if amount_usdc > max_position:
        return {
            'success': False,
            'error': f'Amount exceeds max position size of {max_position:.2f} USDC ({config.trading.max_position_percent}% of portfolio)',
            'requested': amount_usdc
        }
    
    # Execute trade
    result = await client.place_market_buy(symbol, amount_usdc, reason)
    
    # Log trade
    if result['success']:
        await _log_trade(result)
    
    return result


async def sell_coin(symbol: str, percentage: float, reason: str) -> Dict:
    """
    Sell coin holdings back to USDC.
    
    Args:
        symbol: Coin to sell (e.g., 'BTC' or 'BTCUSDC')
        percentage: Percentage of holdings to sell (1-100)
        reason: Reason for the trade
    
    Returns:
        Trade result
    """
    client = await get_binance_client()
    config = get_config()
    quote = config.trading.quote_currency
    
    # Ensure we have the full trading pair
    if not symbol.upper().endswith(quote):
        symbol = f"{symbol.upper()}{quote}"
    
    # Validate percentage
    percentage = max(1, min(100, percentage))
    
    # Execute trade
    result = await client.place_market_sell(symbol, percentage=percentage, reason=reason)
    
    # Log trade
    if result['success']:
        await _log_trade(result)
    
    return result


async def _log_trade(trade: Dict) -> None:
    """Log a trade to the trade history file."""
    config = get_config()
    history_path = config.data_dir / "trade_history.json"
    
    # Load existing history
    try:
        with open(history_path, 'r') as f:
            history = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        history = []
    
    # Append new trade
    history.append(trade)
    
    # Save updated history
    with open(history_path, 'w') as f:
        json.dump(history, f, indent=2)


async def get_trade_history(limit: int = 20) -> List[Dict]:
    """Get recent trade history from local logs."""
    config = get_config()
    history_path = config.data_dir / "trade_history.json"
    
    try:
        with open(history_path, 'r') as f:
            history = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        history = []
    
    return history[-limit:]


async def find_best_momentum_trade() -> Dict[str, Any]:
    """
    Find the best momentum trade opportunity right now.
    Pre-analyzes top gainers and returns a recommendation ready to execute.
    Uses scalping parameters when scalping mode is enabled.
    
    Returns:
        Trade recommendation with symbol, score, and suggested action
    """
    client = await get_binance_client()
    config = get_config()
    
    # Get scalping settings
    is_scalping = config.scalping.enabled
    min_volume = config.scalping.min_volume_usdc if is_scalping else 50_000
    target_profit = config.scalping.target_profit_percent if is_scalping else 3.0
    
    # Get top gainers
    gainers = await client.get_top_gainers(20)
    
    # Filter for tradeable opportunities
    opportunities = []
    for coin in gainers:
        change = coin['priceChangePercent']
        volume = coin['volume']
        
        # Scalping: Need higher volume for quick exits
        if volume < min_volume:
            continue
            
        # Sweet spot for scalping: 3-15% gain (not overextended)
        # For regular trading: 3-20%
        max_change = 15 if is_scalping else 20
        if not (3 <= change <= max_change):
            continue
            
        # Calculate a score - scalping favors volume more
        volume_weight = 2.5 if is_scalping else 2.0
        volume_score = min(volume / 500_000, volume_weight)
        momentum_score = min(change / 10, 1.5)
        # Scalping penalizes extended moves more
        extension_penalty = max(0, (change - 12) * 0.15) if is_scalping else max(0, (change - 15) * 0.1)
        
        score = volume_score + momentum_score - extension_penalty
        
        opportunities.append({
            'symbol': coin['symbol'],
            'baseAsset': coin['baseAsset'],
            'change_24h': round(change, 2),
            'volume_usdc': round(volume, 0),
            'score': round(score, 2),
            'risk': 'low' if change < 8 else ('medium' if change < 12 else 'high')
        })
    
    # Sort by score
    opportunities.sort(key=lambda x: x['score'], reverse=True)
    
    if not opportunities:
        return {
            'found': False,
            'message': 'No good scalping opportunities. Market may be quiet or volume too low.',
            'suggestion': 'Wait 10 seconds for next check.'
        }
    
    best = opportunities[0]
    mode_label = "SCALPING" if is_scalping else "MOMENTUM"
    return {
        'found': True,
        'mode': mode_label,
        'recommendation': best,
        'all_opportunities': opportunities[:5],
        'target_profit_percent': target_profit,
        'suggested_action': f"BUY {best['baseAsset']} with ALL available USDC. Target: +{target_profit}% profit",
        'reasoning': f"[{mode_label}] {best['baseAsset']} up {best['change_24h']}% with ${best['volume_usdc']:,.0f} volume. Score: {best['score']}/4.0"
    }


# Tool definitions for DeepSeek function calling
BINANCE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_portfolio",
            "description": "Get current portfolio holdings, USDC balance, and total value. Use this to understand your current position before making decisions.",
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
            "name": "get_top_gainers",
            "description": "Get the top gaining cryptocurrencies in the last 24 hours. Returns price change %, volume, and momentum indicators.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of top gainers to return (default: 10, max: 50)",
                        "default": 10
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_coin_stats",
            "description": "Get detailed 24-hour statistics for a specific coin including price change, high/low, volume, and momentum classification.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Coin symbol like 'BTC', 'ETH', or full pair like 'BTCUSDC'"
                    }
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "buy_coin",
            "description": "Buy a cryptocurrency using USDC. Validates against portfolio rules (max position size, reserve requirements). Always provide a clear reason.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Coin to buy (e.g., 'BTC', 'ETH', 'SOL')"
                    },
                    "amount_usdc": {
                        "type": "number",
                        "description": "Amount of USDC to spend on this purchase"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Clear explanation for why you're making this trade"
                    }
                },
                "required": ["symbol", "amount_usdc", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "sell_coin",
            "description": "Sell cryptocurrency holdings back to USDC. Can sell a percentage of holdings. Always provide a clear reason.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string", 
                        "description": "Coin to sell (e.g., 'BTC', 'ETH', 'SOL')"
                    },
                    "percentage": {
                        "type": "number",
                        "description": "Percentage of holdings to sell (1-100). Use 100 to sell all."
                    },
                    "reason": {
                        "type": "string",
                        "description": "Clear explanation for why you're selling"
                    }
                },
                "required": ["symbol", "percentage", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_trade_history",
            "description": "Get your recent trade history to analyze past decisions and performance.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of recent trades to return (default: 20)",
                        "default": 20
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_best_momentum_trade",
            "description": "Find the BEST momentum trading opportunity right now. Returns a pre-analyzed recommendation with score. Use this when you want to trade but aren't sure which coin to pick.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]
