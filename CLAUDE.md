# Claude Code Startup Guide

**👋 Welcome to the VWAP Prediction System!**

This guide helps you quickly understand the codebase when you start a new session.

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

## 🎯 Essential Reading (Read These First)

### 1. **[docs/ALGORITHM.md](docs/ALGORITHM.md)** - How It Works
**Read this to understand the core logic**

Key concepts:
- **Detection**: Sliding window (300s) finds repetitive (stock, volume) patterns
- **Prediction**: Linear extrapolation using rate from last 2 points
  ```python
  rate = (current - previous) / time_span_minutes
  prediction = current + (rate × 15)
  ```
- **VWAP Calculation**: Cumulative sum of (volume × price) / 1 billion
- **Three Metrics**: BU (buy-up), SD (sell-down), BUSD (difference)

**Why it works:**
- Algorithmic traders use repetitive order patterns
- Rate-based prediction captures momentum
- 15-minute horizon balances accuracy vs usefulness

### 2. **[docs/ANALYTICS_GUIDE.md](docs/ANALYTICS_GUIDE.md)** - How To Use
**Read this to help users with the system**

Key points:
- **Frontend GUI**: http://localhost:8050 (controls everything, no manual tmux!)
- **Backend tmux**: Session `vwap-backend` (auto-managed by frontend)
- **Data Access**: Ray shared memory via `pload('vwap_predictions')`
- **Controls**: Day selector, speed slider (1x-100x), Update button

### 3. **[docs/DATA_FORMAT.md](docs/DATA_FORMAT.md)** - Data Structure
**Read this to understand input/output data**

Key facts:
- **Input**: SSI HOSE BUSD JSON (line-delimited)
- **Location**: `/d/data/ssi/ws/YYYY_MM_DD_ssi_hose_busd.received.txt`
- **Requirement**: Post-KRX data only (May 2025+) - needs `serverTime` field
- **Output**: DataFrame in Ray with timestamp, current VWAPs, predictions

## 🏗️ Architecture Overview

```
Data Flow:
---------
SSI BUSD file (stdin)
    ↓
Parser (core/parser.py) - Extracts bubbles from JSON
    ↓
Detector (core/detector.py) - Sliding window pattern detection
    ↓
Predictor (core/predictor.py) - Rate-based linear extrapolation
    ↓
Ray Shared Memory - Inter-process communication
    ↓
Frontend (vwap_prediction_frontend.py) - Dash dashboard

Backend Control:
---------------
Frontend GUI → tmux session 'vwap-backend' → Backend process
```

## 📍 System Locations

### Frontend
- **File**: `vwap_prediction_frontend.py`
- **URL**: http://localhost:8050
- **Process Manager**: PM2 (`pm2 start ecosystem.config.js`)
- **Controls**: Day selector, replay speed, backend restart

### Backend
- **File**: `vwap_prediction_backend.py`
- **Tmux Session**: `vwap-backend`
- **Command**: `cat <data_file> | python vwap_prediction_backend.py --speed <X>`
- **Management**: Automatically controlled by frontend GUI

### Data
- **Input Directory**: `/d/data/ssi/ws/`
- **File Pattern**: `YYYY_MM_DD_ssi_hose_busd.received.txt`
- **Valid Dates**: May 2025 onwards (post-KRX only)
- **Shared Memory**: Ray (`pload('vwap_predictions')`)

### Configuration
- **Python Environment**: `/Users/m2/anaconda3/envs/quantum/bin/python`
- **Detection Window**: 300 seconds
- **Prediction Interval**: 15 seconds (data time)
- **Prediction Horizon**: 15 minutes

## 🔑 Key Files

### Core Logic
- `core/parser.py` - Parses SSI BUSD JSON → Bubble objects
- `core/detector.py` - FastVWAPDetector (sliding window)
- `core/predictor.py` - VWAPPredictor (rate-based)

### Main Applications
- `vwap_prediction_backend.py` - Streaming processor (runs in tmux)
- `vwap_prediction_frontend.py` - Dash dashboard with backend control
- `verify_predictions.py` - Verification script

### Support Files
- `backend_controller.py` - Backend process management
- `metis/ray_core.py` - Ray shared memory utilities
- `ecosystem.config.js` - PM2 configuration

## 💡 Common User Tasks

### "How do I start the system?"
```bash
# 1. Start frontend (controls everything)
pm2 start ecosystem.config.js

# 2. Open browser
# Go to http://localhost:8050

# 3. Use GUI to control backend
# - Select trading day
# - Set replay speed
# - Click "Update Dashboard"
# The frontend automatically manages tmux!
```

### "How do I access the data programmatically?"
```python
from metis import gen_ray_functions

_, _, psave, pload = gen_ray_functions()
df = pload('vwap_predictions')

# DataFrame columns:
# - timestamp, effective_timestamp, datetime
# - bu_current, sd_current, busd_current
# - bu_pred_15min, sd_pred_15min, busd_pred_15min
```

### "How do I check backend logs?"
```bash
# Attach to tmux (Ctrl+B, D to detach)
tmux attach -t vwap-backend

# Or list sessions
tmux ls
```

### "Why is there no data for April 2025?"
Pre-KRX data lacks the `serverTime` field. Parser requires this field and will skip data from April 2025 and earlier. See `core/parser.py:78-85` for implementation.

### "How do predictions work?"
1. Every 15 seconds (data time), system calculates rate from last 2 points
2. Rate = (current - previous) / time_span_minutes
3. Prediction = current + (rate × 15 minutes)
4. Based on momentum, assumes linear continuation

See `core/predictor.py` for implementation.

## 🐛 Debugging Tips

### No data showing in dashboard?
1. Check tmux: `tmux attach -t vwap-backend`
2. Check Ray: `pload('vwap_predictions')` returns None?
3. Check file exists: `ls /d/data/ssi/ws/*2025_11_27*.txt`
4. Check it's post-KRX (May 2025+)

### Backend not restarting?
1. Frontend sends Ctrl+C to tmux
2. Check tmux session exists: `tmux ls | grep vwap-backend`
3. Check frontend logs: `pm2 logs vwap-frontend`
4. See `vwap_prediction_frontend.py:62` (restart_backend function)

### Predictions don't match formula?
Run verification script:
```bash
python verify_predictions.py
```

## 📚 Additional Documentation

**For specific tasks:**
- Algorithm details → [docs/ALGORITHM.md](docs/ALGORITHM.md)
- Data analysis → [docs/ANALYTICS_GUIDE.md](docs/ANALYTICS_GUIDE.md)
- Data format → [docs/DATA_FORMAT.md](docs/DATA_FORMAT.md)
- Historical context → [docs/HISTORICAL_COMPARISON.md](docs/HISTORICAL_COMPARISON.md)
- Documentation index → [docs/README.md](docs/README.md)

**Main README**: [README.md](README.md)

## 🎓 Understanding the Domain

### What is VWAP?
Volume-Weighted Average Price = Cumulative Σ(volume × price) / 1 billion

Tracks institutional money flow. Large institutional orders create detectable patterns.

### What are BU/SD/BUSD?
- **BU**: Buy-up VWAP (uptick trades, price ≥ previous)
- **SD**: Sell-down VWAP (downtick trades, price ≤ previous)
- **BUSD**: BU - SD (net institutional pressure)

### Why detect patterns?
Algorithmic traders use repetitive (stock, volume) tuples to execute large orders gradually. Detecting these patterns reveals institutional flow.

### Why linear prediction?
Simple, fast, interpretable. Rate-based extrapolation captures short-term momentum (15 min). More complex models risk overfitting.

## 🚀 Quick Confidence Checklist

Before helping users, verify you understand:

- [ ] Detection uses 300s sliding window to find repetitive patterns
- [ ] Prediction uses rate from last 2 points × 15 min horizon
- [ ] Frontend is Dash dashboard at localhost:8050
- [ ] Backend runs in tmux session 'vwap-backend'
- [ ] Frontend GUI controls backend (no manual tmux needed)
- [ ] Data in Ray shared memory: `pload('vwap_predictions')`
- [ ] Only post-KRX data works (May 2025+)
- [ ] Three metrics: BU (buy), SD (sell), BUSD (difference)

## 🎯 Your Role

As Claude Code, you help users:
1. **Understand** the system (refer to docs above)
2. **Analyze** VWAP data (use Analytics Guide)
3. **Debug** issues (check tmux, Ray, data files)
4. **Extend** functionality (understand algorithm first)
5. **Export** data (see Analytics Guide examples)

**Always remember**: Users control everything via GUI at http://localhost:8050. They don't need to touch tmux manually!

---

**Last Updated**: 2025-11-28

Built with Claude Code
