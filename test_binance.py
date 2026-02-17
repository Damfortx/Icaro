"""Test Binance connection"""
import asyncio
from src.exchange.binance_client import get_binance_client

async def test():
    print("Testing Binance connection...")
    try:
        client = await get_binance_client()
        print("✓ Client initialized")
        
        balance = await client.get_account_balance()
        print(f"✓ Got balances: {len(balance)} assets")
        
        for asset, bal in balance.items():
            print(f"  {asset}: {bal['total']:.4f}")
        
        usdc = await client.get_usdc_balance()
        print(f"\n✓ USDC available: ${usdc:.2f}")
        
        pairs = await client.get_tradeable_pairs()
        print(f"✓ Tradeable USDC pairs: {len(pairs)}")
        
        gainers = await client.get_top_gainers(5)
        print(f"✓ Top 5 gainers:")
        for g in gainers:
            print(f"  {g['baseAsset']}: {g['priceChangePercent']:+.2f}%")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
