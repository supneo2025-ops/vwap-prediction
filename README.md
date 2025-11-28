# VWAP Prediction System

Real-time VWAP (Volume-Weighted Average Price) detection and prediction system for SSI HOSE BUSD data.

## Features

- **Real-time VWAP Detection**: Detects VWAP patterns using sliding window analysis
- **Rate-Based Predictions**: Predicts future VWAP values 15 minutes ahead
- **Timestamp-Based Replay**: Replays historical data at configurable speeds (1x-100x)
- **Interactive Dashboard**: Dash-Plotly dashboard with live charts
- **Ray Shared Memory**: High-performance inter-process communication

## Quick Start

```bash
# Start backend (in tmux)
tmux new -s vwap-backend
cat /d/data/ssi/ws/2025_11_27_ssi_hose_busd.received.txt | python vwap_prediction_backend.py --speed 5.0

# Start frontend (PM2)
pm2 start ecosystem.config.js
```

Access dashboard at: http://localhost:8050

## Data Requirements

- HOSE SSI BUSD files must be **post-KRX (May 2025 onward)** because the parser depends on the `serverTime` field that KRX introduced.
- Data from April 2025 and earlier lacks this field and will be skipped, so the system cannot replay or predict on those days.

## Analytics & Research

For data analysis and research workflows, see the **[Analytics Guide](docs/ANALYTICS_GUIDE.md)**:
- GUI controls for replay (no manual tmux needed!)
- Programmatic data access via Ray
- Example analysis scripts
- Export formats and workflows

## Prediction Formula

```python
rate = (current - previous) / time_span_minutes
prediction = current + (rate × 15)
```

## Configuration

- Detection window: 300s
- Prediction interval: 15s (data time)
- Prediction horizon: 15 minutes
- Data cutoff: 14:40:00
- Dashboard update: 200ms

## Documentation

### For Users
- **[Analytics Guide](docs/ANALYTICS_GUIDE.md)** - How to use the system for data analysis
- **[Algorithm](docs/ALGORITHM.md)** - How detection and prediction work
- **[Data Format](docs/DATA_FORMAT.md)** - Input/output data specifications
- **[Documentation Index](docs/README.md)** - Complete documentation overview

### For AI Assistants
- **[CLAUDE.md](CLAUDE.md)** - Quick startup guide for Claude Code
- **[AGENTS.md](AGENTS.md)** - Quick startup guide for Codex and other AI agents

Built with Claude Code
