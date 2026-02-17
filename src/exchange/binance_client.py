"""
Binance Exchange Client for Icaro Trading Bot.
Handles all interactions with Binance API (Spot trading).
"""

import asyncio
from typing import Dict, List, Optional, Tuple
from decimal import Decimal, ROUND_DOWN
from binance.client import Client
from binance.exceptions import BinanceAPIException
from datetime import datetime

from src.config import get_config


class BinanceClient:
    """Wrapper around python-binance for spot trading operations."""
    
    # Testnet API endpoints
    TESTNET_API_URL = 'https://testnet.binance.vision/api'
    TESTNET_WS_URL = 'wss://testnet.binance.vision/ws'
    
    def __init__(self):
        self.config = get_config()
        self.client = self._create_client()
        self._exchange_info: Dict = {}
        self._symbol_filters: Dict[str, Dict] = {}
    
    def _create_client(self) -> Client:
        """Create Binance client with appropriate configuration."""
        client = Client(
            api_key=self.config.binance.api_key,
            api_secret=self.config.binance.api_secret,
            testnet=self.config.binance.testnet
        )
        
        if self.config.binance.testnet:
            client.API_URL = self.TESTNET_API_URL
        
        # Sync time with Binance servers to avoid -1021 timestamp errors
        # This calculates the offset between local time and server time
        try:
            server_time = client.get_server_time()
            local_time = int(datetime.now().timestamp() * 1000)
            time_offset = server_time['serverTime'] - local_time
            client.timestamp_offset = time_offset
        except Exception:
            # If we can't sync time, continue anyway - may fail on signed requests
            pass
            
        return client
    
    async def initialize(self) -> None:
        """Initialize exchange info and symbol filters."""
        loop = asyncio.get_event_loop()
        self._exchange_info = await loop.run_in_executor(
            None, self.client.get_exchange_info
        )
        
        # Cache symbol filters for order validation
        for symbol_info in self._exchange_info.get('symbols', []):
            symbol = symbol_info['symbol']
            self._symbol_filters[symbol] = {
                'filters': {f['filterType']: f for f in symbol_info['filters']},
                'baseAsset': symbol_info['baseAsset'],
                'quoteAsset': symbol_info['quoteAsset'],
                'status': symbol_info['status']
            }
    
    async def get_account_balance(self) -> Dict[str, float]:
        """Get all non-zero balances."""
        loop = asyncio.get_event_loop()
        account = await loop.run_in_executor(None, self.client.get_account)
        
        balances = {}
        for balance in account['balances']:
            free = float(balance['free'])
            locked = float(balance['locked'])
            total = free + locked
            if total > 0:
                balances[balance['asset']] = {
                    'free': free,
                    'locked': locked,
                    'total': total
                }
        
        return balances
    
    async def get_usdc_balance(self) -> float:
        """Get available USDC balance."""
        balances = await self.get_account_balance()
        usdc = balances.get('USDC', {})
        return usdc.get('free', 0.0)
    
    async def get_tradeable_pairs(self) -> List[Dict]:
        """Get all tradeable USDC pairs."""
        quote = self.config.trading.quote_currency
        pairs = []
        
        for symbol, info in self._symbol_filters.items():
            if info['quoteAsset'] == quote and info['status'] == 'TRADING':
                pairs.append({
                    'symbol': symbol,
                    'baseAsset': info['baseAsset'],
                    'quoteAsset': info['quoteAsset']
                })
        
        return pairs
    
    async def get_ticker_price(self, symbol: str) -> float:
        """Get current price for a symbol."""
        loop = asyncio.get_event_loop()
        ticker = await loop.run_in_executor(
            None, lambda: self.client.get_symbol_ticker(symbol=symbol)
        )
        return float(ticker['price'])
    
    async def get_all_tickers(self) -> Dict[str, float]:
        """Get prices for all symbols."""
        loop = asyncio.get_event_loop()
        tickers = await loop.run_in_executor(None, self.client.get_all_tickers)
        return {t['symbol']: float(t['price']) for t in tickers}
    
    async def get_24h_stats(self, symbol: str) -> Dict:
        """Get 24-hour statistics for a symbol."""
        loop = asyncio.get_event_loop()
        stats = await loop.run_in_executor(
            None, lambda: self.client.get_ticker(symbol=symbol)
        )
        
        return {
            'symbol': symbol,
            'priceChange': float(stats['priceChange']),
            'priceChangePercent': float(stats['priceChangePercent']),
            'highPrice': float(stats['highPrice']),
            'lowPrice': float(stats['lowPrice']),
            'volume': float(stats['volume']),
            'quoteVolume': float(stats['quoteVolume']),
            'lastPrice': float(stats['lastPrice'])
        }
    
    async def get_top_gainers(self, limit: int = 10) -> List[Dict]:
        """Get top gaining coins in the last 24 hours (USDC pairs only)."""
        loop = asyncio.get_event_loop()
        all_tickers = await loop.run_in_executor(None, self.client.get_ticker)
        
        quote = self.config.trading.quote_currency
        usdc_tickers = [
            t for t in all_tickers 
            if t['symbol'].endswith(quote)
        ]
        
        # Sort by price change percent (descending)
        sorted_tickers = sorted(
            usdc_tickers,
            key=lambda x: float(x['priceChangePercent']),
            reverse=True
        )
        
        result = []
        for t in sorted_tickers[:limit]:
            result.append({
                'symbol': t['symbol'],
                'baseAsset': t['symbol'].replace(quote, ''),
                'priceChangePercent': float(t['priceChangePercent']),
                'lastPrice': float(t['lastPrice']),
                'volume': float(t['quoteVolume'])  # Volume in USDC
            })
        
        return result
    
    def _get_lot_size_filter(self, symbol: str) -> Tuple[Decimal, Decimal, Decimal]:
        """Get LOT_SIZE filter values (minQty, maxQty, stepSize)."""
        filters = self._symbol_filters.get(symbol, {}).get('filters', {})
        lot_size = filters.get('LOT_SIZE', {})
        
        return (
            Decimal(lot_size.get('minQty', '0.00001')),
            Decimal(lot_size.get('maxQty', '99999999')),
            Decimal(lot_size.get('stepSize', '0.00001'))
        )
    
    def _get_notional_filter(self, symbol: str) -> Decimal:
        """Get minimum notional value for a symbol."""
        filters = self._symbol_filters.get(symbol, {}).get('filters', {})
        notional = filters.get('NOTIONAL', filters.get('MIN_NOTIONAL', {}))
        return Decimal(notional.get('minNotional', '1.0'))
    
    def _adjust_quantity(self, symbol: str, quantity: float) -> float:
        """Adjust quantity to comply with LOT_SIZE filter."""
        min_qty, max_qty, step_size = self._get_lot_size_filter(symbol)
        qty = Decimal(str(quantity))
        
        # Round down to step size
        qty = (qty // step_size) * step_size
        
        # Ensure within bounds
        qty = max(min_qty, min(qty, max_qty))
        
        return float(qty)
    
    async def place_market_buy(
        self, 
        symbol: str, 
        amount_usdc: float,
        reason: str = ""
    ) -> Dict:
        """
        Place a market buy order using USDC.
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDC')
            amount_usdc: Amount of USDC to spend
            reason: Reason for the trade (for logging)
        
        Returns:
            Order result dictionary
        """
        # Validate minimum notional
        min_notional = float(self._get_notional_filter(symbol))
        if amount_usdc < min_notional:
            return {
                'success': False,
                'error': f'Order value {amount_usdc:.2f} USDC is below minimum notional of {min_notional} USDC.',
                'symbol': symbol,
                'amount_usdc': amount_usdc,
                'min_notional': min_notional,
                'timestamp': datetime.now().isoformat()
            }
        
        # Place order using quoteOrderQty - this buys using USDC amount directly
        # This is faster (no need to fetch price) and avoids LOT_SIZE rounding issues
        loop = asyncio.get_event_loop()
        try:
            order = await loop.run_in_executor(
                None,
                lambda: self.client.order_market_buy(
                    symbol=symbol,
                    quoteOrderQty=amount_usdc  # Spend exactly this much USDC
                )
            )
            
            # Calculate effective price from executed order
            executed_qty = float(order['executedQty'])
            executed_quote = float(order['cummulativeQuoteQty'])
            effective_price = executed_quote / executed_qty if executed_qty > 0 else 0
            
            return {
                'success': True,
                'orderId': order['orderId'],
                'symbol': symbol,
                'side': 'BUY',
                'quantity': executed_qty,
                'price': float(order['fills'][0]['price']) if order['fills'] else effective_price,
                'total_usdc': executed_quote,
                'reason': reason,
                'timestamp': datetime.now().isoformat()
            }
            
        except BinanceAPIException as e:
            return {
                'success': False,
                'error': str(e),
                'symbol': symbol,
                'amount_usdc': amount_usdc,
                'timestamp': datetime.now().isoformat()
            }
    
    async def place_market_sell(
        self,
        symbol: str,
        quantity: Optional[float] = None,
        percentage: float = 100.0,
        reason: str = ""
    ) -> Dict:
        """
        Place a market sell order.
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDC')
            quantity: Exact quantity to sell (optional)
            percentage: Percentage of holdings to sell (if quantity not specified)
            reason: Reason for the trade (for logging)
        
        Returns:
            Order result dictionary
        """
        # Get current balance if quantity not specified
        if quantity is None:
            base_asset = self._symbol_filters[symbol]['baseAsset']
            balances = await self.get_account_balance()
            available = balances.get(base_asset, {}).get('free', 0)
            quantity = available * (percentage / 100.0)
        
        quantity = self._adjust_quantity(symbol, quantity)
        
        # Validate minimum notional
        price = await self.get_ticker_price(symbol)
        notional = quantity * price
        min_notional = float(self._get_notional_filter(symbol))
        
        if notional < min_notional:
            raise ValueError(f"Order value {notional:.2f} USDC is below minimum {min_notional}")
        
        loop = asyncio.get_event_loop()
        try:
            order = await loop.run_in_executor(
                None,
                lambda: self.client.order_market_sell(
                    symbol=symbol,
                    quantity=quantity
                )
            )
            
            return {
                'success': True,
                'orderId': order['orderId'],
                'symbol': symbol,
                'side': 'SELL',
                'quantity': float(order['executedQty']),
                'price': float(order['fills'][0]['price']) if order['fills'] else price,
                'total_usdc': float(order['cummulativeQuoteQty']),
                'reason': reason,
                'timestamp': datetime.now().isoformat()
            }
            
        except BinanceAPIException as e:
            return {
                'success': False,
                'error': str(e),
                'symbol': symbol,
                'quantity': quantity,
                'timestamp': datetime.now().isoformat()
            }
    
    async def get_order_history(self, symbol: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Get recent order history."""
        loop = asyncio.get_event_loop()
        
        if symbol:
            orders = await loop.run_in_executor(
                None,
                lambda: self.client.get_all_orders(symbol=symbol, limit=limit)
            )
        else:
            # Get orders for all USDC pairs we've traded
            orders = []
            # Note: In real implementation, we'd track traded symbols
            
        return orders


# Singleton instance
_client: Optional[BinanceClient] = None

async def get_binance_client() -> BinanceClient:
    """Get the global Binance client instance."""
    global _client
    if _client is None:
        _client = BinanceClient()
        await _client.initialize()
    return _client
