# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## System Overview
n**Note**: Real-time monitoring systems have been moved to separate repositories:
- [CoinRedS](../CoinRedS) - 45-day MA envelope alert system (10-min intervals)
- [Upbit1515](../Upbit1515) - Upbit market crash detection (1-hour intervals)

### Core Architecture

```
universe_selector.py → Get Top 100 coins (CoinGecko)
         ↓
auto_debug_builder.py → Batch simulate all coins (Binance 5Y data)
         ↓
core/phase1_5_core.py → State machine simulation
         ↓
debug/{SYMBOL}_debug.csv → Full trading history per coin
         ↓
coin_analysis_excel.py → Generate current trading targets Excel
         ↓

```

**Data Flow:**
1. **Universe Selection**: CoinGecko API → Top 100 coins (filtered: no wrapped tokens, no stablecoins)
2. **Simulation**: Binance API → 5Y daily OHLCV → Phase 1.5 state machine → CSV debug files
3. **Analysis**: Latest CSV + CoinGecko current price → Excel report with next buy targets
4. **Monitoring**: Real-time price checks → Telegram alerts on opportunities

## Commands

### Initial Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file with Telegram credentials
cat > .env << EOF
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
EOF
```

### Core Workflow

```bash
# Step 1: Select universe (Top 100 coins)
python universe_selector.py --asset coin --save

# Step 2: Generate simulations for all coins (2-5 minutes)
python auto_debug_builder.py

# Step 3: Generate current trading analysis Excel
python coin_analysis_excel.py
```

### Real-Time Monitoring

**OMG has its own real-time monitoring:**
- [crypto_realtime_monitor.py](./crypto_realtime_monitor.py) - Phase 1.5 buy-level proximity alerts (30-min intervals)

**Separate monitoring systems:**
- [CoinRedS](../CoinRedS) - 45-day MA envelope alerts
- [Upbit1515](../Upbit1515) - Upbit market crash detection


### Analysis Tools

```bash
# Analyze stop-loss triggers across all coins
python analyze_stop_loss_commonality.py

# Check excluded coins from universe
python check_excluded_coins.py

# Test special case handling
python check_special_cases.py
```

### Single Coin Testing

```bash
# Run Phase 1.5 simulation for single coin (legacy)
cd Old
python run_phase1_5.py --symbol BTC --limit-days 180
```

## Phase 1.5 Trading Strategy

### State Machine (2 Modes)

**High Mode:**
- Tracks **H** (highest price in current cycle)
- Monitors for deep correction
- **Transition**: When `low ≤ H × 0.56` (-44%) → switch to **wait mode**
- No buy/sell operations allowed in high mode

**Wait Mode:**
- Tracks **L** (lowest price in current cycle)
- Allows buy/add/sell operations
- **Transition**: When `high ≥ L × 1.985` (+98.5%) → **RESTART** event

**RESTART Event:**
- Triggered by +98.5% rebound from L
- Clears all position data, forbidden levels, cutoff price
- Resets: `H = current high`, `mode = high`, `L = None`
- Starts new cycle fresh

### Buy Levels (B1-B7)

All levels calculated from **H** (highest price in cycle):

| Level | Multiplier | Drop from H | Position Size (Suggested) |
|-------|-----------|-------------|---------------------------|
| B1 | H × 0.56 | -44% | 10% of capital |
| B2 | H × 0.52 | -48% | 10% |
| B3 | H × 0.46 | -54% | 10% |
| B4 | H × 0.41 | -59% | 10% |
| B5 | H × 0.35 | -65% | 20% |
| B6 | H × 0.28 | -72% | 20% |
| B7 | H × 0.21 | -79% | 20% (final) |
| **Stop** | H × 0.19 | -81% | **Exit all** |

**Important Constraints:**
- **Cutoff price**: Once you SELL at a level, you cannot BUY at any level above that price
- **ADD rule**: Can only ADD (pyramid) at deeper levels than last buy
- **One position per coin**: System assumes single consolidated position

### Sell Thresholds

Sell triggers are **stage-dependent** (based on entry stage, rebound from L):

| Entry Stage | Sell Threshold (Rebound from L) |
|-------------|--------------------------------|
| Stage 1 (B1) | +7.7% |
| Stage 2 (B2) | +17.3% |
| Stage 3 (B3) | +24.4% |
| Stage 4 (B4) | +37.4% |
| Stage 5 (B5) | +52.7% |
| Stage 6 (B6) | +79.9% |
| Stage 7 (B7) | +98.5% (full cycle exit) |

**Logic**: Deeper entries require larger rebounds to sell (patience reward).

### Event Types in CSV

- **BUY**: First entry at a level (e.g., `BUY B2`)
- **ADD**: Pyramid into existing position at deeper level (e.g., `ADD B5`)
- **SELL**: Exit due to rebound threshold hit (e.g., `SELL S3`)
- **STOP LOSS**: Exit at -81% from H
- **RESTART_+98.5pct**: Cycle reset on +98.5% rebound from L

### System 1: Envelope Alert


**Strategy**: 45-day moving average with ±45% envelope bands

**Trigger Condition**: Price within 5% of lower band (H×0.55 level)

**Scope**: Top 30 Binance coins (filtered via `universe_selector.py`)

**Execution**: Every 10 minutes (manual run, not scheduled)

**Output**:
- Telegram message with alert summary
- `output/envelope_alerts_{timestamp}.xlsx` - Full analysis

**Alert Format**:
```
🚨 Red S 근접 알림 🚨
---
순위 | 코인 | 거리
1 | BTC | -2.3%
2 | ETH | -4.1%
```

### System 2: Upbit Monitor


**Strategy**: Detect market-wide crashes on Upbit KRW pairs

**Trigger Condition**: ≥15 coins with -15% daily drop

**Scope**: All KRW-pair coins on Upbit (~500 coins)

**Execution**: Every hour (on the hour)

**Deduplication**: Maximum 1 START alert + 1 END alert per day (tracked in `alert_status.json`)

**Output**:
- Telegram message on crisis start/end
- `Red S/upbit_monitor_{YYYYMMDD}.log` - Hourly logs
- `Red S/alert_status.json` - Daily alert tracking

**Alert Logic**:
- **START**: First time condition met on a day → Send alert
- **ONGOING**: Condition still met, but START already sent → Log only, no alert
- **END**: Condition no longer met after START → Send recovery alert

## Key Files

### Core Python Scripts

- **universe_selector.py**: Fetches Top 100 coins from CoinGecko, excludes wrapped tokens and stablecoins
- **auto_debug_builder.py**: Batch simulator - fetches 5Y daily data from Binance, runs Phase 1.5 simulation for all coins
- **core/phase1_5_core.py**: State machine implementation (514 lines) - handles mode transitions, buy/sell logic, event tracking
- **coin_analysis_excel.py**: Reads latest debug CSVs, fetches current prices, calculates next buy targets, generates Excel report
- **phase1_5_rules.py**: Buy-level constraint rules (cutoff, forbidden levels, stage-based sell thresholds)
- **config/adapters.py**: Binance API client (public endpoints, no auth required)

### Analysis Tools

- **analyze_stop_loss_commonality.py**: Analyze stop-loss patterns across all coins
- **analyze_stop_loss_ranking.py**: Rank coins by stop-loss frequency
- **check_excluded_coins.py**: Verify coin exclusion logic (wrapped tokens, stablecoins)
- **check_special_cases.py**: Test edge cases in state machine

### Data Files

**Debug CSVs** (`debug/{SYMBOL}_debug.csv`):
- Full simulation history (1500+ rows per coin)
- 27 columns: OHLCV, state, events, levels, forecasts
- Event rows (BUY/ADD/SELL/RESTART) + daily snapshots
- Used as source-of-truth for current state

**Analysis Excel** (`output/coin_analysis_{timestamp}.xlsx`):
- Current trading opportunities for Top 100 coins
- Columns: Rank, Symbol, Market Cap, Current Price, H value, Next Buy Level, Distance %
- Sorted by closest opportunities first

**Envelope Alert Excel** (`output/envelope_alerts_{timestamp}.xlsx`):
- 45-day MA envelope analysis for Top 30 coins
- Columns: Rank, Symbol, Price, MA45, Lower Band, Distance %

## CSV Output Structure

### Debug CSV Columns (27 total)

**OHLCV** (5 columns):
- `date`, `open`, `high`, `low`, `close`

**State Machine** (5 columns):
- `mode`: "high" or "wait"
- `position`: TRUE/FALSE (holding or not)
- `stage`: 1-7 (entry stage number)
- `event`: BUY/ADD/SELL/STOP LOSS/RESTART (blank for snapshots)
- `basis`: "LOW" or "HIGH" (basis for current operation)

**Market State** (4 columns):
- `H`: Highest price in current cycle
- `L_now`: Current lowest price in cycle
- `rebound_from_L_pct`: Current rebound % from L
- `threshold_pct`: Sell threshold for current stage

**Buy Levels** (9 columns):
- `B1` through `B7`: 7 buy levels calculated from H
- `Stop_Loss`: Stop loss price (H × 0.19)
- `cutoff_price`: Forbidden buy level (from last sell)

**Forecast** (4 columns):
- `next_buy_level_name`: Next actionable buy level (e.g., "B2")
- `next_buy_level_price`: Target price for next buy
- `next_buy_trigger_price`: Low price to trigger next buy
- `forbidden_levels_above_last_sell`: Comma-separated list of forbidden levels

### Row Types

1. **Event Rows**: Non-empty `event` column (BUY, ADD, SELL, STOP LOSS, RESTART)
2. **Snapshot Rows**: Empty `event` column (end-of-day state capture)
3. **Ordering**: Events sorted by type priority (BUY → ADD → SELL → STOP LOSS), then snapshot

### Example Event Row

```csv
date,open,high,low,close,mode,position,stage,event,basis,H,L_now,rebound_from_L_pct,threshold_pct,B1,B2,...
2025-02-03,3.31,3.83,2.39,3.65,wait,TRUE,2,BUY B2,LOW,5.37,2.63,17.3,17.3,3.01,2.79,...
```

## API Integration

### CoinGecko API

- **Endpoint**: `/api/v3/coins/markets`
- **Authentication**: None (public API)
- **Rate Limit**: ~50 calls/min (handled via backoff in `universe_selector.py`)
- **Purpose**: Market cap rankings, current prices, 24h change %

### Binance API

- **Endpoint**: `/api/v3/klines`
- **Authentication**: None (public API)
- **Rate Limit**: 1200 weight/min (handled via pagination in `config/adapters.py`)
- **Purpose**: Historical daily OHLCV (up to 5 years)
- **Pagination**: 1500 bars per request, auto-paginated for 5Y data

### Upbit API

- **Endpoint**: `/v1/ticker`
- **Authentication**: None (public API)
- **Rate Limit**: ~10 calls/sec (handled in `upbit_monitor.py`)
- **Purpose**: Real-time KRW-pair ticker data (all coins)

### Telegram Bot API

- **Endpoint**: `https://api.telegram.org/bot{TOKEN}/sendMessage`
- **Configuration**: `.env` file with `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
- **Message Format**: HTML formatting supported
- **Rate Limit**: 30 messages/sec (not a concern for this use case)

## Technical Details

### Coin Universe Exclusions

**Excluded Symbols** (hard-coded in `universe_selector.py`):
```python
EXCLUDE_SYMBOLS = {"WBTC", "WETH", "WBETH", "STETH", "WSTETH", "WEETH", "USD1", "BFUSD", "BNSOL", "BNB", "ENA"}
EXCLUDE_NAME_KEYWORDS = {"WRAPPED", "BRIDGE"}
```

**Rationale**: Wrapped tokens track underlying asset price, no independent trading value.

### Data Precision

- **Calculations**: 10 decimal places (Python float)
- **CSV Output**: 6-10 decimals depending on column
- **Excel Display**: 2-4 decimals for readability

### Timezone Handling

- **Binance**: UTC timestamps
- **Conversion**: UTC → KST (UTC+9) in some scripts (check `auto_debug_builder.py`)
- **Storage**: Debug CSVs use UTC dates (YYYY-MM-DD format)

### Error Handling

- **API Failures**: Exponential backoff (1s → 2s → 4s → 8s)
- **Missing Data**: Skip coin and log error (no partial simulations)
- **Telegram Failures**: Log error but continue execution

## Important Conventions

### File Organization

- **Simulations**: `debug/` directory (CSV and Excel files)
- **Analysis**: `output/` directory (timestamped Excel files)
- **Monitoring**: `Red S/` directory (all real-time systems)
- **Legacy**: `Old/` directory (deprecated scripts, keep for reference)

### Data Persistence

- **Debug CSVs**: Full historical simulation data (source of truth)
- **Alert Status**: `Red S/alert_status.json` (daily reset at midnight)
- **No Database**: Everything file-based for transparency

### Naming Conventions

- **Symbols**: Always uppercase (BTC, ETH, SOL)
- **Filenames**: Lowercase symbol in paths (`debug/btc_debug.csv`)
- **Timestamps**: `YYYYMMDD_HHMMSS` format in output filenames

### Code Modification Guidelines

- **Core logic changes**: Test on single coin first (`Old/run_phase1_5.py`)
- **API changes**: Check rate limits before deployment
- **Batch operations**: Always add progress logging (% complete)
- **Telegram messages**: Keep concise (<4096 chars, Telegram limit)

## Troubleshooting

### Common Issues

**Debug files not generating:**
- Check Binance API connectivity: `python -c "from config.adapters import BinanceClient; print(BinanceClient().get_klines('BTCUSDT', '1d', limit=10))"`
- Verify symbol format: Must be uppercase, no special chars
- Check disk space: Each coin generates ~500KB CSV

**Telegram alerts not sending:**
- Verify `.env` file exists in project root
- Test token: `python -c "from Red\ S.telegram_notifier import TelegramNotifier; TelegramNotifier('YOUR_TOKEN').send_message('YOUR_CHAT_ID', 'test')"`
- Check bot permissions: Must have "Send Messages" permission

**Excel generation fails:**
- Install openpyxl: `pip install openpyxl`
- Check file locks: Close Excel before running scripts
- Verify debug CSVs exist: `ls debug/*.csv | wc -l` (should see ~100 files)

**Monitoring not alerting:**
- Check proximity threshold: Default 5% for envelope, -15% for Upbit
- Verify schedule: Envelope runs manually, Upbit runs hourly
- Check alert status: `cat Red\ S/alert_status.json` (may have daily limit hit)

## Known Limitations

1. **No Real Trading**: Information system only, no order execution
2. **Daily Resolution**: Simulations use daily candles, no intraday data
3. **Single Position**: System assumes one position per coin (no partial exits tracked)
4. **Manual Batch Updates**: No auto-scheduler for `auto_debug_builder.py` (run manually when needed)
5. **No Backtesting Metrics**: Simulations generate events but no P&L, Sharpe, or drawdown stats
6. **Telegram Only**: No email, SMS, or other notification channels

## Related Documentation

This project has companion documentation files that provide additional context:

- **MONITORING_SCHEDULE_SUMMARY.md**: Scheduled monitoring configurations
- **REALTIME_MONITORING_GUIDE.md**: Detailed guide for real-time alert systems
- **SCHEDULER_SETUP.md**: Windows Task Scheduler configuration (if applicable)
- **TELEGRAM_SETUP.md**: Step-by-step Telegram bot setup guide
- **CONVERSATION_SUMMARY.md**: Development history and decision rationale

## Dependencies

```
pandas
openpyxl
requests
python-dotenv
schedule  # For Red S/run_monitor.py
```

Install with: `pip install -r requirements.txt`

## Architecture Notes

### Separation of Concerns

- **Universe Selection**: `universe_selector.py` (independent, reusable)
- **Simulation Engine**: `core/phase1_5_core.py` (pure state machine, no I/O)
- **Batch Processing**: `auto_debug_builder.py` (orchestrates API + simulation)
- **Analysis Generation**: `coin_analysis_excel.py` (reads CSVs, generates Excel)
- **Real-Time Monitoring**: `Red S/` directory (independent from simulation system)

### Why CSV as Intermediate Format

The system uses CSV files as the primary data interchange format:
- ✅ Human-readable for manual inspection
- ✅ Easy to version control (git-friendly)
- ✅ Can be opened in Excel for quick checks
- ✅ No database setup required
- ⚠️ Requires careful file locking (close Excel before running scripts)
- ⚠️ No concurrent write support (sequential execution only)

### State Machine Design

The Phase 1.5 core is implemented as a **pure state machine**:
- **Input**: OHLCV dataframe
- **Output**: Extended dataframe with state columns and events
- **No side effects**: No API calls, no file I/O, no prints
- **Testable**: Can run simulations on synthetic data
- **Deterministic**: Same input always produces same output

This design allows for:
1. Easy unit testing
2. Reproducible backtests
3. Clear separation from data fetching
4. Potential parallelization in future
