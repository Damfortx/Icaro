"""
Icaro - AI Trading Bot
Main entry point for the trading bot.

Usage:
    python -m src.main [--dry-run] [--once]
    
Options:
    --dry-run   Run without executing actual trades (simulation mode)
    --once      Run a single decision cycle and exit
"""

import asyncio
import argparse
import signal
import sys
from datetime import datetime
from typing import Optional

from src.config import get_config
from src.exchange.binance_client import get_binance_client
from src.agent.deepseek_agent import get_agent
from src.agent.tools.binance_tools import get_portfolio, get_top_gainers
from src.agent.tools.portfolio_tools import calculate_performance
from src.telegram_bot import get_telegram_notifier
from src.state import get_state_manager
from src.utils.logger import (
    console,
    logger,
    print_header,
    print_portfolio,
    print_top_gainers,
    print_decision,
    print_status,
    print_countdown
)


# Global flag for graceful shutdown
running = True
telegram_notifier = None
state_manager = None


def signal_handler(sig, frame):
    """Handle shutdown signals."""
    global running, state_manager
    console.print("\n[yellow]Shutting down gracefully...[/yellow]")
    running = False
    
    # Save state before exit
    if state_manager:
        console.print("[yellow]Saving state...[/yellow]")
        state_manager._save()


async def send_trade_notifications(decision: dict):
    """Send Telegram notifications for any trades executed."""
    global telegram_notifier, state_manager
    
    if not telegram_notifier:
        return
    
    actions = decision.get('actions', [])
    for action in actions:
        tool = action.get('tool', '')
        if tool in ['buy_coin', 'sell_coin']:
            result = action.get('result', {})
            if result.get('success'):
                # Add side to result if not present
                if 'side' not in result:
                    result['side'] = 'BUY' if tool == 'buy_coin' else 'SELL'
                
                # Record trade in state
                if state_manager:
                    state_manager.record_trade(result)
                
                await telegram_notifier.send_trade_notification(result)


async def run_decision_cycle(dry_run: bool = False) -> dict:
    """
    Run a single decision cycle.
    
    Args:
        dry_run: If True, don't execute actual trades
    
    Returns:
        Decision result from the agent
    """
    global state_manager
    config = get_config()
    agent = get_agent()
    
    # Get current state for display
    portfolio = await get_portfolio()
    top_gainers = await get_top_gainers(10)
    
    # Update state with current portfolio
    if state_manager:
        state_manager.update_portfolio(portfolio)
    
    # Display current state
    console.print("\n" + "=" * 60)
    console.print(f"[bold]📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/bold]")
    
    # Show state summary
    if state_manager:
        summary = state_manager.get_summary()
        console.print(f"[dim]Cycles: {summary['decision_cycles']} | Trades: {summary['total_trades']} | P&L: {summary['profit_percent']:+.2f}%[/dim]")
    
    console.print("=" * 60)
    
    print_portfolio(portfolio)
    console.print()
    print_top_gainers(top_gainers)
    
    # Let AI make decision
    console.print("\n[bold cyan]🤖 AI is analyzing the market...[/bold cyan]\n")
    
    context = None
    if dry_run:
        context = "NOTE: Running in DRY-RUN mode. Do NOT execute actual trades, only analyze and recommend."
    
    decision = await agent.decide(context)
    print_decision(decision)
    
    # Record decision in state
    if state_manager and decision.get('success'):
        state_manager.record_decision(decision)
    
    # Send Telegram notifications for trades
    if not dry_run and decision.get('success'):
        await send_trade_notifications(decision)
    
    return decision


async def main_loop(dry_run: bool = False):
    """
    Main trading loop.
    
    Args:
        dry_run: If True, don't execute actual trades
    """
    global running, telegram_notifier, state_manager
    config = get_config()
    
    # Initialize state manager
    state_manager = get_state_manager()
    console.print(f"[green]✓ State manager initialized[/green]")
    
    # Show previous session info
    summary = state_manager.get_summary()
    if summary['decision_cycles'] > 0:
        console.print(f"[cyan]📊 Resuming: {summary['decision_cycles']} cycles, {summary['total_trades']} trades, {summary['profit_percent']:+.2f}% P&L[/cyan]")
    
    # Initialize Telegram bot
    telegram_notifier = get_telegram_notifier()
    telegram_notifier.get_portfolio_func = get_portfolio
    telegram_notifier.get_performance_func = calculate_performance
    
    try:
        await telegram_notifier.initialize()
        await telegram_notifier.start_polling()
        console.print("[green]✓ Telegram bot started[/green]")
    except Exception as e:
        console.print(f"[yellow]⚠️ Telegram bot failed to start: {e}[/yellow]")
    
    # Initialize Binance client
    console.print("[yellow]Initializing Binance client...[/yellow]")
    try:
        client = await get_binance_client()
        mode = "TESTNET" if config.binance.testnet else "PRODUCTION"
        console.print(f"[green]✓ Binance client initialized ({mode})[/green]")
    except Exception as e:
        console.print(f"[red]✗ Failed to initialize Binance client: {e}[/red]")
        return
    
    # Validate API connection
    try:
        balance = await client.get_usdc_balance()
        console.print(f"[green]✓ API connection verified. USDC Balance: ${balance:.2f}[/green]")
        
        # Send startup notification
        await telegram_notifier.send_notification(
            f"🚀 <b>Icaro iniciado</b>\n\n"
            f"<b>Modo:</b> {'Producción' if not config.binance.testnet else 'Testnet'}\n"
            f"<b>Balance USDC:</b> ${balance:.2f}\n"
            f"<b>Ciclos previos:</b> {summary['decision_cycles']}\n"
            f"<b>Trades previos:</b> {summary['total_trades']}\n\n"
            f"<i>Bot listo para trading 24/7</i>"
        )
    except Exception as e:
        console.print(f"[red]✗ API connection failed: {e}[/red]")
        console.print("[yellow]Make sure your API keys are correct and have proper permissions.[/yellow]")
        return
    
    # Validate DeepSeek API
    if not config.deepseek.api_key:
        console.print("[red]✗ DeepSeek API key not configured. Add DEEPSEEK_API_KEY to .env[/red]")
        return
    
    console.print(f"[green]✓ DeepSeek API key configured[/green]")
    
    if dry_run:
        console.print("[yellow]⚠️  Running in DRY-RUN mode - No actual trades will be executed[/yellow]")
    
    console.print("\n[bold green]🚀 Starting trading loop...[/bold green]")
    console.print(f"[dim]Decision interval: {config.agent.decision_interval_seconds} seconds[/dim]")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")
    
    cycle_start = datetime.now()
    
    # Main loop
    while running:
        try:
            await run_decision_cycle(dry_run)
            
            # Track runtime
            if state_manager:
                elapsed = (datetime.now() - cycle_start).seconds
                state_manager.add_runtime(elapsed)
                cycle_start = datetime.now()
            
            # Wait for next cycle
            if running:
                interval = config.agent.decision_interval_seconds
                print_countdown(interval)
                
                # Sleep in small increments to allow quick shutdown
                for _ in range(interval):
                    if not running:
                        break
                    await asyncio.sleep(1)
                    
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Error in decision cycle: {e}")
            console.print(f"[red]Error: {e}[/red]")
            console.print("[yellow]Waiting 30 seconds before retry...[/yellow]")
            await asyncio.sleep(30)
    
    # Save final state
    if state_manager:
        state_manager._save()
        console.print("[green]✓ State saved[/green]")
    
    # Cleanup
    if telegram_notifier:
        summary = state_manager.get_summary() if state_manager else {}
        await telegram_notifier.send_notification(
            f"👋 <b>Icaro detenido</b>\n\n"
            f"<b>Ciclos completados:</b> {summary.get('decision_cycles', 0)}\n"
            f"<b>Trades totales:</b> {summary.get('total_trades', 0)}\n"
            f"<b>P&L:</b> {summary.get('profit_percent', 0):+.2f}%"
        )
        await telegram_notifier.stop()
    
    console.print("[bold green]👋 Icaro stopped. Goodbye![/bold green]")


async def run_once(dry_run: bool = False):
    """Run a single decision cycle and exit."""
    global telegram_notifier, state_manager
    config = get_config()
    
    # Initialize state manager
    state_manager = get_state_manager()
    
    # Initialize Telegram for notifications
    telegram_notifier = get_telegram_notifier()
    telegram_notifier.get_portfolio_func = get_portfolio
    telegram_notifier.get_performance_func = calculate_performance
    
    try:
        await telegram_notifier.initialize()
    except:
        pass
    
    # Initialize Binance client
    console.print("[yellow]Initializing...[/yellow]")
    try:
        client = await get_binance_client()
    except Exception as e:
        console.print(f"[red]Failed to initialize: {e}[/red]")
        return
    
    # Run single cycle
    await run_decision_cycle(dry_run)
    
    # Save state
    if state_manager:
        state_manager._save()


def main():
    """Entry point."""
    parser = argparse.ArgumentParser(description="Icaro AI Trading Bot")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without executing actual trades"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single decision cycle and exit"
    )
    
    args = parser.parse_args()
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Print header
    print_header()
    
    # Show configuration
    config = get_config()
    console.print(f"[dim]Mode: {'Testnet' if config.binance.testnet else 'Production'}[/dim]")
    console.print(f"[dim]Model: {config.deepseek.model}[/dim]")
    console.print(f"[dim]Quote Currency: {config.trading.quote_currency}[/dim]")
    console.print()
    
    # Run
    if args.once:
        asyncio.run(run_once(args.dry_run))
    else:
        asyncio.run(main_loop(args.dry_run))


if __name__ == "__main__":
    main()
