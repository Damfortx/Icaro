"""
DeepSeek Agent for Icaro Trading Bot.
Main AI agent that makes trading decisions using function calling.
"""

import json
import asyncio
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from openai import AsyncOpenAI

from src.config import get_config
from src.agent.system_prompt import get_prompt_manager
from src.agent.tools.binance_tools import (
    BINANCE_TOOLS,
    get_portfolio,
    get_top_gainers,
    get_coin_stats,
    buy_coin,
    sell_coin,
    get_trade_history,
    find_best_momentum_trade
)
from src.agent.tools.portfolio_tools import (
    PORTFOLIO_TOOLS,
    calculate_performance,
    update_strategy,
    get_learnings
)
from src.agent.tools.research_tools import (
    RESEARCH_TOOLS,
    research_coin,
    search_crypto_news,
    check_market_sentiment
)


class DeepSeekAgent:
    """
    AI Trading Agent powered by DeepSeek LLM.
    Uses function calling to interact with Binance and make trading decisions.
    """
    
    def __init__(self):
        self.config = get_config()
        self.prompt_manager = get_prompt_manager()
        
        # Initialize OpenAI-compatible client for DeepSeek
        self.client = AsyncOpenAI(
            api_key=self.config.deepseek.api_key,
            base_url=self.config.deepseek.base_url
        )
        
        # Combine all tools
        self.tools = BINANCE_TOOLS + PORTFOLIO_TOOLS + RESEARCH_TOOLS
        
        # Map function names to implementations
        self.tool_functions: Dict[str, Callable] = {
            # Binance tools
            "get_portfolio": get_portfolio,
            "get_top_gainers": get_top_gainers,
            "get_coin_stats": get_coin_stats,
            "buy_coin": buy_coin,
            "sell_coin": sell_coin,
            "get_trade_history": get_trade_history,
            "find_best_momentum_trade": find_best_momentum_trade,
            # Portfolio tools
            "calculate_performance": calculate_performance,
            "update_strategy": update_strategy,
            "get_learnings": get_learnings,
            # Research tools
            "research_coin": research_coin,
            "search_crypto_news": search_crypto_news,
            "check_market_sentiment": check_market_sentiment,
        }
        
        # Conversation history for context
        self.conversation_history: List[Dict] = []
        self.max_history_length = 20
    
    async def _execute_tool(self, name: str, arguments: Dict) -> Any:
        """Execute a tool function and return the result."""
        func = self.tool_functions.get(name)
        if not func:
            return {"error": f"Unknown tool: {name}"}
        
        try:
            # Check if the function is async
            if asyncio.iscoroutinefunction(func):
                result = await func(**arguments)
            else:
                result = func(**arguments)
            return result
        except Exception as e:
            return {"error": str(e)}
    
    async def decide(self, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Make a trading decision based on current market state.
        
        Args:
            context: Additional context to provide to the AI
        
        Returns:
            Decision result with actions taken
        """
        # Load current system prompt
        system_prompt = self.prompt_manager.load()
        
        # Build user message with context
        user_message = self._build_context_message(context)
        
        # Start fresh for each decision cycle to avoid orphaned tool messages
        # This prevents the "tool must follow tool_calls" error
        session_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        # Call DeepSeek with tools
        try:
            response = await self.client.chat.completions.create(
                model=self.config.deepseek.model,
                messages=session_messages,
                tools=self.tools,
                tool_choice="auto",
                temperature=self.config.deepseek.temperature,
                max_tokens=self.config.deepseek.max_tokens
            )
        except Exception as e:
            return {
                "success": False,
                "error": f"DeepSeek API error: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
        
        message = response.choices[0].message
        actions_taken = []
        
        # Process tool calls iteratively
        max_iterations = 10  # Prevent infinite loops
        iteration = 0
        
        while message.tool_calls and iteration < max_iterations:
            iteration += 1
            
            # Add assistant message with tool_calls to session
            assistant_msg = {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in message.tool_calls
                ]
            }
            session_messages.append(assistant_msg)
            
            # Execute each tool call and collect results
            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}
                
                # Execute the tool
                result = await self._execute_tool(func_name, arguments)
                
                actions_taken.append({
                    "tool": func_name,
                    "arguments": arguments,
                    "result": result
                })
                
                # Add tool result immediately after the assistant message
                session_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, default=str)
                })
            
            # Get next response from model
            try:
                response = await self.client.chat.completions.create(
                    model=self.config.deepseek.model,
                    messages=session_messages,
                    tools=self.tools,
                    tool_choice="auto",
                    temperature=self.config.deepseek.temperature,
                    max_tokens=self.config.deepseek.max_tokens
                )
                message = response.choices[0].message
            except Exception as e:
                return {
                    "success": False,
                    "error": f"DeepSeek API error during tool handling: {str(e)}",
                    "actions": actions_taken,
                    "timestamp": datetime.now().isoformat()
                }
        
        return {
            "success": True,
            "response": message.content,
            "actions": actions_taken,
            "timestamp": datetime.now().isoformat()
        }
    
    def _build_context_message(self, additional_context: Optional[str] = None) -> str:
        """Build the context message for the AI."""
        now = datetime.now()
        
        message = f"""Current time: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC-5

⚡ ACTION TIME - Make a trade decision NOW.

MANDATORY ACTIONS:
1. get_portfolio - Check available USDC
2. get_top_gainers OR find_best_momentum_trade - Find opportunities
3. DECIDE: BUY or SELL

💰 CAPITAL STRATEGY (Small Portfolio):
- You have ~11 USDC total
- USE ALL AVAILABLE USDC per trade (keep only 1 USDC reserve)
- Example: If you have 10 USDC available, buy with 10 USDC, not 5
- Bigger position = bigger absolute profit

TRADING RULES:
- Got 5+ USDC available? → Find a trade and go ALL IN
- Holding a coin up +2-3%? → SELL and take profit  
- Holding a coin down -5%? → SELL and cut loss
- Target coins up 5-15% with high volume

⚠️ DO NOT split into small trades - use your full buying power
⚠️ IGNORE stuck positions worth < 5 USDC (like PEPE)

After trading, briefly explain what you did.
"""
        
        if additional_context:
            message += f"\nAdditional context: {additional_context}"
        
        return message
    
    def reset_conversation(self) -> None:
        """Reset the conversation history."""
        self.conversation_history = []


# Singleton instance
_agent: Optional[DeepSeekAgent] = None

def get_agent() -> DeepSeekAgent:
    """Get the global agent instance."""
    global _agent
    if _agent is None:
        _agent = DeepSeekAgent()
    return _agent
