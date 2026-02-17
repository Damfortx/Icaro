"""
Logging utilities for Icaro Trading Bot.
Provides rich console output and file logging.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.logging import RichHandler

from src.config import get_config


# Rich console for pretty output
console = Console()

# Configure logging
def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Setup logging with Rich handler."""
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)]
    )
    return logging.getLogger("icaro")


logger = setup_logging()


def print_header():
    """Print the Icaro header."""
    header = """
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   ██╗ ██████╗ █████╗ ██████╗  ██████╗                    ║
║   ██║██╔════╝██╔══██╗██╔══██╗██╔═══██╗                   ║
║   ██║██║     ███████║██████╔╝██║   ██║                   ║
║   ██║██║     ██╔══██║██╔══██╗██║   ██║                   ║
║   ██║╚██████╗██║  ██║██║  ██║╚██████╔╝                   ║
║   ╚═╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝                    ║
║                                                           ║
║            AI Trading Bot powered by DeepSeek             ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
"""
    console.print(header, style="bold cyan")


def print_portfolio(portfolio: dict):
    """Print portfolio summary in a nice table."""
    table = Table(title="📊 Portfolio", show_header=True, header_style="bold magenta")
    table.add_column("Asset", style="cyan")
    table.add_column("Quantity", justify="right")
    table.add_column("Price", justify="right", style="yellow")
    table.add_column("Value (USDC)", justify="right", style="green")
    
    # Add USDC balance
    table.add_row(
        "USDC",
        f"{portfolio.get('usdc_available', 0):.2f}",
        "$1.00",
        f"${portfolio.get('usdc_available', 0):.2f}"
    )
    
    # Add holdings
    for holding in portfolio.get('holdings', []):
        table.add_row(
            holding['asset'],
            f"{holding['quantity']:.6f}",
            f"${holding['price']:.4f}",
            f"${holding['value_usdc']:.2f}"
        )
    
    # Add total
    table.add_section()
    table.add_row(
        "[bold]TOTAL[/bold]",
        "",
        "",
        f"[bold green]${portfolio.get('total_value_usdc', 0):.2f}[/bold green]"
    )
    
    console.print(table)


def print_top_gainers(gainers: list):
    """Print top gainers table."""
    table = Table(title="🚀 Top Gainers (24h)", show_header=True, header_style="bold green")
    table.add_column("#", style="dim")
    table.add_column("Coin", style="cyan")
    table.add_column("Price", justify="right")
    table.add_column("Change", justify="right")
    table.add_column("Volume", justify="right", style="dim")
    
    for i, gainer in enumerate(gainers[:10], 1):
        change = gainer['priceChangePercent']
        change_style = "green" if change > 0 else "red"
        
        table.add_row(
            str(i),
            gainer['baseAsset'],
            f"${gainer['lastPrice']:.4f}",
            f"[{change_style}]{change:+.2f}%[/{change_style}]",
            f"${gainer['volume']:,.0f}"
        )
    
    console.print(table)


def print_decision(decision: dict):
    """Print an AI decision."""
    if decision.get('success'):
        # Print actions taken
        actions = decision.get('actions', [])
        if actions:
            console.print("\n[bold yellow]🤖 AI Actions:[/bold yellow]")
            for action in actions:
                tool = action.get('tool', 'unknown')
                args = action.get('arguments', {})
                
                if tool in ['buy_coin', 'sell_coin']:
                    result = action.get('result', {})
                    if result.get('success'):
                        emoji = "🟢" if tool == 'buy_coin' else "🔴"
                        console.print(f"  {emoji} {tool}: {args.get('symbol')} - {args.get('reason', 'No reason')}")
                    else:
                        console.print(f"  ⚠️ {tool} failed: {result.get('error', 'Unknown error')}")
        
        # Print AI response
        response = decision.get('response')
        if response:
            console.print(Panel(response, title="💭 AI Thoughts", border_style="blue"))
    else:
        console.print(f"[red]❌ Decision failed: {decision.get('error')}[/red]")


def print_trade(trade: dict):
    """Print a trade execution result."""
    if trade.get('success'):
        side = trade.get('side', 'UNKNOWN')
        emoji = "🟢 BUY" if side == 'BUY' else "🔴 SELL"
        
        console.print(Panel(
            f"{emoji} {trade.get('symbol')}\n"
            f"Quantity: {trade.get('quantity', 0):.6f}\n"
            f"Price: ${trade.get('price', 0):.4f}\n"
            f"Total: ${trade.get('total_usdc', 0):.2f} USDC\n"
            f"Reason: {trade.get('reason', 'N/A')}",
            title="💰 Trade Executed",
            border_style="green" if side == 'BUY' else "red"
        ))
    else:
        console.print(f"[red]❌ Trade failed: {trade.get('error')}[/red]")


def print_status(message: str, style: str = ""):
    """Print a status message."""
    console.print(f"[{style}]{message}[/{style}]" if style else message)


def print_countdown(seconds: int):
    """Print a countdown timer."""
    console.print(f"[dim]Next decision in {seconds} seconds...[/dim]")
