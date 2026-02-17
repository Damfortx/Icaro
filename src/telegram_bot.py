"""
Telegram Bot Integration for Icaro Trading Bot.
Provides notifications and interactive commands for monitoring.
"""

import os
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from src.config import get_config


class TelegramNotifier:
    """
    Telegram bot for notifications and interactive commands.
    
    Features:
    - Send trade notifications
    - Answer questions about current status
    - Report portfolio balance
    """
    
    def __init__(self):
        self.token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.bot: Optional[Bot] = None
        self.app: Optional[Application] = None
        self.chat_ids: set = set()  # Store authorized chat IDs
        self._initialized = False
        
        # Reference to agent (set externally)
        self.agent = None
        self.get_portfolio_func = None
        self.get_performance_func = None
    
    async def initialize(self):
        """Initialize the Telegram bot."""
        if not self.token:
            print("⚠️ Telegram bot token not configured")
            return
        
        self.app = Application.builder().token(self.token).build()
        self.bot = self.app.bot
        
        # Register handlers
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("status", self._cmd_status))
        self.app.add_handler(CommandHandler("portfolio", self._cmd_portfolio))
        self.app.add_handler(CommandHandler("trades", self._cmd_trades))
        self.app.add_handler(CommandHandler("help", self._cmd_help))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
        
        self._initialized = True
        print("✓ Telegram bot initialized")
    
    async def start_polling(self):
        """Start the bot polling in the background."""
        if not self._initialized:
            await self.initialize()
        
        if self.app:
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()
    
    async def stop(self):
        """Stop the bot."""
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
    
    async def send_notification(self, message: str, parse_mode: str = "HTML"):
        """Send a notification to all registered chats."""
        if not self.bot or not self.chat_ids:
            return
        
        for chat_id in self.chat_ids:
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=parse_mode
                )
            except Exception as e:
                print(f"Failed to send Telegram message: {e}")
    
    async def send_trade_notification(self, trade: Dict[str, Any]):
        """Send a formatted trade notification."""
        if not trade.get('success'):
            return
        
        side = trade.get('side', 'UNKNOWN')
        emoji = "🟢" if side == 'BUY' else "🔴"
        
        message = f"""
{emoji} <b>Trade Executed</b>

<b>Action:</b> {side}
<b>Symbol:</b> {trade.get('symbol', 'N/A')}
<b>Quantity:</b> {trade.get('quantity', 0):.6f}
<b>Price:</b> ${trade.get('price', 0):.4f}
<b>Total:</b> ${trade.get('total_usdc', 0):.2f} USDC

<b>Reason:</b> {trade.get('reason', 'N/A')}

<i>🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>
"""
        await self.send_notification(message)
    
    # Command handlers
    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command - register user for notifications."""
        chat_id = update.effective_chat.id
        self.chat_ids.add(chat_id)
        
        await update.message.reply_text(
            "🤖 ¡Hola! Soy Icaro, tu bot de trading.\n\n"
            "Comandos disponibles:\n"
            "/status - Estado actual del bot\n"
            "/portfolio - Ver fondos actuales\n"
            "/trades - Últimas operaciones\n"
            "/help - Más información\n\n"
            "También puedes preguntarme directamente sobre el trading."
        )
    
    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        try:
            # Try to get state manager for comprehensive stats
            try:
                from src.state import get_state_manager
                state_mgr = get_state_manager()
                summary = state_mgr.get_summary()
                
                message = f"""
📊 <b>Estado de Icaro</b>

<b>Tiempo activo:</b> {summary.get('runtime_hours', 0):.1f} horas
<b>Ciclos de decisión:</b> {summary.get('decision_cycles', 0)}
<b>Trades totales:</b> {summary.get('total_trades', 0)}
<b>Posiciones activas:</b> {summary.get('active_positions', 0)}

<b>Capital actual:</b> ${summary.get('current_capital', 0):.2f} USDC
<b>P&L:</b> {summary.get('profit_percent', 0):+.2f}%

<b>Mejor trade:</b> {summary.get('best_trade', 'N/A')}
<b>Peor trade:</b> {summary.get('worst_trade', 'N/A')}

<i>Bot activo y monitoreando mercado 24/7</i>
"""
            except:
                if self.get_performance_func:
                    perf = await self.get_performance_func()
                    message = f"""
📊 <b>Estado de Icaro</b>

<b>Trades totales:</b> {perf.get('total_trades', 0)}
<b>Compras exitosas:</b> {perf.get('successful_buys', 0)}
<b>Ventas exitosas:</b> {perf.get('successful_sells', 0)}
<b>P&L:</b> {perf.get('pnl_percent', 0):+.2f}%

<i>Bot activo y monitoreando mercado 24/7</i>
"""
                else:
                    message = "📊 Bot activo. Usa /portfolio para ver fondos."
            
            await update.message.reply_text(message, parse_mode="HTML")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")
    
    async def _cmd_portfolio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /portfolio command."""
        try:
            if self.get_portfolio_func:
                portfolio = await self.get_portfolio_func()
                
                holdings_text = ""
                for h in portfolio.get('holdings', []):
                    holdings_text += f"  • {h['asset']}: {h['quantity']:.4f} (${h['value_usdc']:.2f})\n"
                
                if not holdings_text:
                    holdings_text = "  Sin posiciones abiertas\n"
                
                message = f"""
💰 <b>Portfolio</b>

<b>USDC disponible:</b> ${portfolio.get('usdc_available', 0):.2f}

<b>Posiciones:</b>
{holdings_text}
<b>Valor total:</b> ${portfolio.get('total_value_usdc', 0):.2f} USDC

<i>🕐 {datetime.now().strftime('%H:%M:%S')}</i>
"""
            else:
                message = "❌ No se puede obtener el portfolio en este momento."
            
            await update.message.reply_text(message, parse_mode="HTML")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")
    
    async def _cmd_trades(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /trades command."""
        try:
            from src.agent.tools.binance_tools import get_trade_history
            trades = await get_trade_history(5)
            
            if not trades:
                await update.message.reply_text("📜 No hay operaciones registradas.")
                return
            
            message = "📜 <b>Últimas operaciones:</b>\n\n"
            for t in trades[-5:]:
                emoji = "🟢" if t.get('side') == 'BUY' else "🔴"
                message += f"{emoji} {t.get('symbol', 'N/A')}: ${t.get('total_usdc', 0):.2f}\n"
            
            await update.message.reply_text(message, parse_mode="HTML")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")
    
    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        message = """
🤖 <b>Icaro Trading Bot</b>

Soy un bot de trading automatizado que usa IA para tomar decisiones de inversión en Binance.

<b>Comandos:</b>
/status - Estado del bot y rendimiento
/portfolio - Ver fondos y posiciones
/trades - Últimas operaciones
/help - Esta ayuda

<b>Preguntas:</b>
También puedes preguntarme cosas como:
• "¿Qué estás haciendo?"
• "¿Cuánto dinero hay?"
• "¿Cómo va el trading?"

<b>Notificaciones:</b>
Te enviaré una notificación cada vez que haga una operación.

<i>⚠️ Recuerda: el trading tiene riesgos.</i>
"""
        await update.message.reply_text(message, parse_mode="HTML")
    
    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular text messages."""
        chat_id = update.effective_chat.id
        self.chat_ids.add(chat_id)
        
        text = update.message.text.lower()
        
        # Simple intent detection
        if any(word in text for word in ['dinero', 'fondos', 'balance', 'cuanto', 'cuánto']):
            await self._cmd_portfolio(update, context)
        elif any(word in text for word in ['haciendo', 'estado', 'status', 'cómo va', 'como va']):
            await self._cmd_status(update, context)
        elif any(word in text for word in ['trades', 'operaciones', 'operación']):
            await self._cmd_trades(update, context)
        else:
            await update.message.reply_text(
                "🤔 No estoy seguro de entender. Prueba con:\n"
                "/status - Estado del bot\n"
                "/portfolio - Ver fondos\n"
                "/trades - Operaciones recientes"
            )


# Singleton instance
_notifier: Optional[TelegramNotifier] = None

def get_telegram_notifier() -> TelegramNotifier:
    """Get the global Telegram notifier instance."""
    global _notifier
    if _notifier is None:
        _notifier = TelegramNotifier()
    return _notifier
