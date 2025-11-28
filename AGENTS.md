# Agent Startup Guide (Codex & AI Assistants)

**🤖 Quick onboarding for AI agents working on VWAP Prediction System**

## 🔄 First Action: Check Recent Commits

**ALWAYS start by checking recent commits to understand what changed:**

```bash
git log --oneline -10  # Last 10 commits
git diff HEAD~1        # What changed in last commit
git status             # Current uncommitted changes
```

**Why this matters:**
- Documentation may be outdated if code recently changed
- Recent commits reveal what's actively being worked on
- Uncommitted changes show work in progress
- Helps you understand current state vs documented state

**Quick context refresh:**
```bash
# See what files changed recently
git log --name-status --oneline -5

# See recent commit messages
git log --pretty=format:"%h - %s (%ar)" -10
```

## TL;DR - Essential Facts

```
System: Real-time VWAP pattern detection & prediction for HOSE stock market
Frontend: http://localhost:8050 (Dash dashboard, controls everything)
Backend: tmux session 'vwap-backend' (auto-managed by frontend GUI)
Data: Ray shared memory - pload('vwap_predictions')
Algorithm: Sliding window detection (300s) + rate-based linear prediction (15min)
Data Requirement: Post-KRX only (May 2025+) - needs serverTime field
```

## 📖 Required Reading (In Order)

### 1. **[docs/ALGORITHM.md](docs/ALGORITHM.md)** ⭐⭐⭐
**Must read to understand what the system does**

**Core concept:**
```python
# Detection: Find repetitive (stock, volume) patterns in 300s window
# Prediction: Linear extrapolation
rate = (current - previous) / time_span_minutes
prediction = current + (rate × 15)
```

**Three metrics tracked:**
- BU VWAP: Buy-up volume × price
- SD VWAP: Sell-down volume × price
- BUSD VWAP: BU - SD (net pressure)

**Why it works:**
- Algorithmic trading creates repetitive patterns
- Rate captures momentum
- 15-min horizon balances accuracy/usefulness

### 2. **[docs/ANALYTICS_GUIDE.md](docs/ANALYTICS_GUIDE.md)** ⭐⭐
**How to use the system and access data**

**Key takeaways:**
- Frontend GUI controls backend automatically (no manual tmux!)
- Access data: `from metis import gen_ray_functions; pload('vwap_predictions')`
- Data updates every 15 seconds (data time)
- Example analysis scripts included

### 3. **[docs/DATA_FORMAT.md](docs/DATA_FORMAT.md)** ⭐
**Data structure and parsing rules**

**Critical info:**
- Input: SSI HOSE BUSD JSON from `/d/data/ssi/ws/`
- Parser requires `serverTime` field → only post-KRX (May 2025+)
- Output: DataFrame with timestamp, current VWAPs, predictions
- Lunch gap compression: 11:30-13:00 removed for smooth rates

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Frontend (http://localhost:8050)                        │
│ - Dash dashboard                                        │
│ - Day selector, speed slider, update button            │
│ - Automatically controls backend via tmux               │
│ - PM2 managed: ecosystem.config.js                     │
└────────────────┬────────────────────────────────────────┘
                 │ Sends commands to tmux
                 ↓
┌─────────────────────────────────────────────────────────┐
│ Backend (tmux session: vwap-backend)                    │
│ - Reads: cat /d/data/ssi/ws/<date>.txt                 │
│ - Processes: vwap_prediction_backend.py --speed <X>    │
│ - Replay speed: 1x to 100x                             │
└────────────────┬────────────────────────────────────────┘
                 │ Writes predictions
                 ↓
┌─────────────────────────────────────────────────────────┐
│ Ray Shared Memory                                       │
│ - Key: 'vwap_predictions'                              │
│ - Type: pandas DataFrame                                │
│ - Updates: Every 15 seconds (data time)                │
└────────────────┬────────────────────────────────────────┘
                 │ Read by frontend & analysis scripts
                 ↓
┌─────────────────────────────────────────────────────────┐
│ Analysis Scripts / Users                                │
│ - verify_predictions.py                                 │
│ - Custom analytics (see ANALYTICS_GUIDE.md)            │
└─────────────────────────────────────────────────────────┘
```

## 📂 Critical File Locations

### Main Applications
| File | Purpose | Notes |
|------|---------|-------|
| `vwap_prediction_backend.py` | Streaming processor | Runs in tmux, reads stdin |
| `vwap_prediction_frontend.py` | Dash dashboard | PM2 managed, port 8050 |
| `verify_predictions.py` | Verification | Check formula correctness |

### Core Logic
| File | Purpose | Key Functions |
|------|---------|---------------|
| `core/parser.py` | Parse SSI JSON | `parse_ssi_busd_line()` |
| `core/detector.py` | Pattern detection | `FastVWAPDetector.add_bubble()` |
| `core/predictor.py` | Predictions | `VWAPPredictor.predict()` |

### Data & Config
| Location | Content |
|----------|---------|
| `/d/data/ssi/ws/` | Input data files (YYYY_MM_DD_ssi_hose_busd.received.txt) |
| `Ray shared memory` | Output DataFrame (key: 'vwap_predictions') |
| `ecosystem.config.js` | PM2 config for frontend |

### Python Environment
```
/Users/m2/anaconda3/envs/quantum/bin/python
```

## 🎮 Frontend Controls

**Dashboard URL**: http://localhost:8050

**Controls:**
1. **Trading Day dropdown** - Select date (only May 2025+ shown)
2. **Replay Speed slider** - 1x to 100x
3. **Update Dashboard button** - Apply changes, restart backend

**What happens on "Update Dashboard" click:**
```python
# Frontend does this automatically (vwap_prediction_frontend.py:62)
1. tmux send-keys -t vwap-backend C-c  # Stop current replay
2. Wait 1 second
3. tmux send-keys -t vwap-backend 'cat <file> | python backend.py --speed X' C-m
```

**User never needs to touch tmux manually!**

## 💾 Data Access Pattern

```python
#!/usr/bin/env python3
from metis import gen_ray_functions

# Initialize Ray functions
_, _, psave, pload = gen_ray_functions()

# Load data
df = pload('vwap_predictions')

if df is None or df.empty:
    print("No data. Backend not running or no data generated yet.")
    exit(1)

# DataFrame columns:
print(df.columns.tolist())
# ['timestamp', 'effective_timestamp', 'datetime',
#  'bu_current', 'sd_current', 'busd_current',
#  'bu_pred_15min', 'sd_pred_15min', 'busd_pred_15min',
#  'pred_datetime_15min']

# Latest data point
last = df.iloc[-1]
print(f"Time: {last['datetime']}")
print(f"BU: {last['bu_current']:.2f}B → {last['bu_pred_15min']:.2f}B (15min)")
```

## ⚙️ Key Configuration

```python
# Detection (core/detector.py)
window_seconds = 300          # 5-minute sliding window
min_occurrences = 5           # Pattern repetition threshold
volume_threshold = 200        # Minimum shares

# Prediction (core/predictor.py)
prediction_interval_sec = 15  # Generate prediction every 15s (data time)
prediction_horizons = [15]    # Predict 15 minutes ahead

# Replay (backend)
replay_speed_multiplier = 1.0 to 100.0  # Configurable via GUI

# Dashboard (frontend)
update_interval_ms = 200      # Chart refresh rate
```

## 🔍 Understanding the Algorithm

### Detection Phase (core/detector.py)
```python
# For each incoming bubble (trade):
1. Add to sliding window (last 300 seconds)
2. Track (stock, volume) occurrences
3. If (stock, vol) appears ≥5 times → it's a VWAP pattern
4. Calculate cumulative VWAP = Σ(volume × price) / 1B
5. Maintain separate BU, SD, BUSD VWAPs
```

### Prediction Phase (core/predictor.py)
```python
# Every 15 seconds (data time):
1. Get current VWAP state
2. Calculate rate from last 2 points:
   rate = (current - previous) / time_span_minutes
3. Predict 15 minutes ahead:
   prediction = current + (rate × 15)
4. Save to Ray shared memory
```

### Lunch Gap Compression (backend)
```python
# Problem: 11:30-13:00 gap creates rate spikes
# Solution: Remove gap from timestamps for smooth rates
11:30 → 11:30
12:00 → 11:30 (compressed)
13:00 → 11:30 (compressed)
13:01 → 11:31 (gap removed)

# Two timestamp columns:
- timestamp: Original market time (for display)
- effective_timestamp: Gap-compressed (for rate calculation)
```

## 🚨 Common Issues

### Issue: "No data available"
**Causes:**
- Backend not running
- Wrong trading day selected
- Pre-KRX data (before May 2025)

**Debug:**
```bash
tmux attach -t vwap-backend  # Check backend logs
python -c "from metis import gen_ray_functions; print(gen_ray_functions()[3]('vwap_predictions'))"
ls /d/data/ssi/ws/*2025_11_27*.txt  # Check file exists
```

### Issue: "Data from April 2025 doesn't work"
**Cause:** Pre-KRX data lacks `serverTime` field

**Fix:** Use May 2025 or later. See `core/parser.py:78-85`:
```python
# serverTime is mandatory (index 12)
try:
    server_time_ms = int(fields[12])
except (ValueError, IndexError):
    return None  # Skip pre-KRX data
```

### Issue: "Predictions don't match formula"
**Verify:**
```bash
python verify_predictions.py
```

Should show differences < 0.01B

## 📊 Output Data Structure

```python
# DataFrame in Ray: 'vwap_predictions'

Row example:
{
    'timestamp': 1732675200123,           # Original HOSE time (ms)
    'effective_timestamp': 1732670700123, # Lunch-gap removed (ms)
    'datetime': Timestamp('2025-11-27 09:00:00.123+0700'),

    'bu_current': 1234.56,    # Current BU VWAP (billions)
    'sd_current': 987.65,     # Current SD VWAP (billions)
    'busd_current': 246.91,   # Current BUSD VWAP (billions)

    'bu_pred_15min': 1250.00,   # BU prediction (15min ahead)
    'sd_pred_15min': 990.00,    # SD prediction (15min ahead)
    'busd_pred_15min': 260.00,  # BUSD prediction (15min ahead)

    'pred_datetime_15min': Timestamp('2025-11-27 09:15:00.123+0700')
}
```

## 🎯 Quick Reference Commands

```bash
# Check frontend status
pm2 status
pm2 logs vwap-frontend

# Check backend status
tmux ls | grep vwap-backend
tmux attach -t vwap-backend  # Ctrl+B, D to detach

# Check data files
ls -lh /d/data/ssi/ws/ | grep 2025

# Verify predictions
python verify_predictions.py

# Access data in Python
python -c "from metis import gen_ray_functions; df=gen_ray_functions()[3]('vwap_predictions'); print(df.tail())"

# Manual backend start (for testing)
cat /d/data/ssi/ws/2025_11_27_ssi_hose_busd.received.txt | \
    /Users/m2/anaconda3/envs/quantum/bin/python vwap_prediction_backend.py --speed 5.0
```

## 🧪 Testing & Verification

### Verify algorithm correctness:
```bash
python verify_predictions.py
# Should show: ✓ All predictions match!
```

### Check data quality:
```python
from metis import gen_ray_functions
df = gen_ray_functions()[3]('vwap_predictions')

# Check for gaps
df['time_diff'] = df['timestamp'].diff()
print(df[df['time_diff'] > 60000])  # Gaps > 60s

# Check for NaN
print(df.isnull().sum())
```

### Test different speeds:
1. Set speed to 1x → Real-time (slow)
2. Set speed to 100x → Fast-forward (for testing)
3. Verify predictions still match formula

## 📚 Documentation Hierarchy

```
README.md                    → Quick start, overview
CLAUDE.md (this file)        → AI assistant startup guide
AGENTS.md                    → Same as CLAUDE.md (for Codex)

docs/
├── README.md                → Documentation index
├── ALGORITHM.md             → ⭐ How detection & prediction work
├── ANALYTICS_GUIDE.md       → ⭐ How to use the system
├── DATA_FORMAT.md           → Input/output data specs
└── HISTORICAL_COMPARISON.md → Evolution from iceberg_detector
```

## 🎓 Domain Knowledge

**VWAP = Volume-Weighted Average Price**
- Institutional traders use VWAP to execute large orders
- Cumulative metric: Σ(volume × price) / 1 billion
- Three types: BU (buy-up), SD (sell-down), BUSD (difference)

**Why patterns matter:**
- Algos split large orders into small, repetitive chunks
- Same (stock, volume) tuple repeating = algorithmic execution
- Detecting patterns reveals institutional flow

**Why linear prediction:**
- Simple, fast, interpretable
- Rate-based extrapolation captures short-term momentum
- 15-minute horizon is practical for trading decisions

## ✅ Pre-work Checklist

Before starting any task, verify you understand:

- [ ] Algorithm: 300s window, find repetitive patterns, predict with rate × 15min
- [ ] Frontend: http://localhost:8050, controls everything via GUI
- [ ] Backend: tmux session 'vwap-backend', auto-managed by frontend
- [ ] Data: Ray shared memory, key 'vwap_predictions', DataFrame
- [ ] Requirement: Post-KRX only (May 2025+), needs serverTime field
- [ ] Three metrics: BU (buy), SD (sell), BUSD (difference)
- [ ] Users don't touch tmux manually - GUI handles it!

## 🤝 Working with Users

**When users ask "How do I...":**
1. Point to Analytics Guide for usage questions
2. Point to Algorithm doc for how it works
3. Show them GUI controls (they don't need CLI!)

**When users report issues:**
1. Check tmux backend logs first
2. Verify data file exists and is post-KRX
3. Check Ray shared memory has data
4. Run verify_predictions.py

**When users want to extend:**
1. Ensure they understand the algorithm first
2. Show relevant source files (core/detector.py, etc.)
3. Emphasize maintaining formula: prediction = current + rate × 15

---

**Last Updated**: 2025-11-28

Built with Claude Code
