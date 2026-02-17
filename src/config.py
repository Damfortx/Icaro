"""
Configuration loader for Icaro Trading Bot.
Loads settings from YAML and environment variables.
"""

import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from dataclasses import dataclass
from typing import List, Dict, Any

# Load environment variables
load_dotenv()

@dataclass
class BinanceConfig:
    api_key: str
    api_secret: str
    testnet: bool

@dataclass
class DeepSeekConfig:
    api_key: str
    model: str
    base_url: str
    temperature: float
    max_tokens: int

@dataclass
class TradingConfig:
    quote_currency: str
    max_position_percent: float
    min_trade_usdc: float
    reserve_usdc: float
    take_profit_levels: List[Dict[str, float]]
    stop_loss_percent: float

@dataclass
class AgentConfig:
    decision_interval_seconds: int
    max_trades_per_hour: int
    research_enabled: bool

@dataclass
class ScalpingConfig:
    enabled: bool
    target_profit_percent: float
    stop_loss_percent: float
    min_volume_usdc: float
    max_hold_minutes: int

@dataclass
class Config:
    binance: BinanceConfig
    deepseek: DeepSeekConfig
    trading: TradingConfig
    agent: AgentConfig
    scalping: ScalpingConfig
    
    # Paths
    base_dir: Path
    data_dir: Path
    config_dir: Path


def load_config() -> Config:
    """Load configuration from settings.yaml and environment variables."""
    
    base_dir = Path(__file__).parent.parent
    config_path = base_dir / "config" / "settings.yaml"
    
    with open(config_path, 'r', encoding='utf-8') as f:
        settings = yaml.safe_load(f)
    
    # Binance config
    binance = BinanceConfig(
        api_key=os.getenv('BINANCE_API_KEY', ''),
        api_secret=os.getenv('BINANCE_API_SECRET', ''),
        testnet=settings['binance'].get('testnet', True)
    )
    
    # DeepSeek config
    deepseek = DeepSeekConfig(
        api_key=os.getenv('DEEPSEEK_API_KEY', ''),
        model=settings['deepseek'].get('model', 'deepseek-chat'),
        base_url=settings['deepseek'].get('base_url', 'https://api.deepseek.com/v1'),
        temperature=settings['deepseek'].get('temperature', 0.7),
        max_tokens=settings['deepseek'].get('max_tokens', 4096)
    )
    
    # Trading config
    trading_settings = settings['trading']
    trading = TradingConfig(
        quote_currency=trading_settings.get('quote_currency', 'USDC'),
        max_position_percent=trading_settings.get('max_position_percent', 50),
        min_trade_usdc=trading_settings.get('min_trade_usdc', 1.0),
        reserve_usdc=trading_settings.get('reserve_usdc', 1.0),
        take_profit_levels=trading_settings.get('take_profit_levels', []),
        stop_loss_percent=trading_settings.get('stop_loss_percent', 10)
    )
    
    # Agent config
    agent_settings = settings['agent']
    agent = AgentConfig(
        decision_interval_seconds=agent_settings.get('decision_interval_seconds', 60),
        max_trades_per_hour=agent_settings.get('max_trades_per_hour', 10),
        research_enabled=agent_settings.get('research_enabled', True)
    )
    
    # Scalping config
    scalping_settings = settings.get('scalping', {})
    scalping = ScalpingConfig(
        enabled=scalping_settings.get('enabled', False),
        target_profit_percent=scalping_settings.get('target_profit_percent', 1.0),
        stop_loss_percent=scalping_settings.get('stop_loss_percent', 1.0),
        min_volume_usdc=scalping_settings.get('min_volume_usdc', 100000),
        max_hold_minutes=scalping_settings.get('max_hold_minutes', 5)
    )
    
    return Config(
        binance=binance,
        deepseek=deepseek,
        trading=trading,
        agent=agent,
        scalping=scalping,
        base_dir=base_dir,
        data_dir=base_dir / "data",
        config_dir=base_dir / "config"
    )


# Global config instance
_config: Config = None

def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config
