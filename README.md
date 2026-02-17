# Icaro - AI Trading Bot

Bot de trading autónomo que utiliza DeepSeek LLM para tomar decisiones de trading en Binance Spot.

## 🚀 Quick Start

### 1. Instalar dependencias

```bash
cd d:\Proyectos\Icaro
pip install -r requirements.txt
```

### 2. Configurar credenciales

Edita el archivo `.env` con tus API keys:

```env
# Binance API (ya configurado para testnet)
BINANCE_API_KEY=tu_api_key
BINANCE_API_SECRET=tu_api_secret

# DeepSeek API (necesario)
DEEPSEEK_API_KEY=tu_deepseek_api_key
```

### 3. Ejecutar el bot

```bash
# Modo completo (loop continuo)
python -m src.main

# Solo una decisión (para pruebas)
python -m src.main --once

# Modo simulación (sin trades reales)
python -m src.main --dry-run
```

## 📁 Estructura del Proyecto

```
Icaro/
├── src/
│   ├── main.py              # Entry point
│   ├── config.py            # Configuration loader
│   ├── agent/
│   │   ├── deepseek_agent.py    # AI agent principal
│   │   ├── system_prompt.py     # Prompt dinámico
│   │   └── tools/
│   │       ├── binance_tools.py     # Trading operations
│   │       ├── portfolio_tools.py   # Portfolio analysis
│   │       └── research_tools.py    # Web research
│   ├── exchange/
│   │   └── binance_client.py    # Binance API wrapper
│   └── utils/
│       └── logger.py            # Rich console logging
├── data/
│   ├── system_prompt.md     # Prompt del AI (editable)
│   ├── trade_history.json   # Historial de trades
│   └── learnings.json       # Aprendizajes del AI
├── config/
│   └── settings.yaml        # Configuración
├── .env                     # API keys (no commitear)
└── requirements.txt
```

## 🔧 Configuración

Edita `config/settings.yaml` para ajustar:

- `binance.testnet`: `true` para testnet, `false` para producción
- `trading.max_position_percent`: Máximo % del portfolio en una moneda
- `trading.min_trade_usdc`: Mínimo para una operación
- `agent.decision_interval_seconds`: Frecuencia de decisiones

## 🤖 Cómo Funciona

1. **Sistema Dinámico**: El AI tiene un system prompt en `data/system_prompt.md` que puede modificar para aprender
2. **Tools disponibles**:
   - `get_portfolio`: Ver holdings actuales
   - `get_top_gainers`: Ver mejores monedas 24h
   - `buy_coin`: Comprar con razón documentada
   - `sell_coin`: Vender con razón documentada
   - `update_strategy`: Guardar aprendizajes
3. **Auto-mejora**: El AI registra sus aprendizajes y ajusta su estrategia

## ⚠️ Notas Importantes

- Actualmente configurado para **Binance Testnet**
- Cambia `binance.testnet` a `false` para operar con dinero real
- El bot respeta las reglas de Binance automáticamente
- Siempre mantiene una reserva de USDC configurada

## 📊 Monitoreo

El bot muestra en consola:
- Portfolio actual
- Top gainers del mercado
- Decisiones del AI
- Trades ejecutados

Los datos se guardan en:
- `data/trade_history.json`: Historial de operaciones
- `data/learnings.json`: Aprendizajes estructurados
