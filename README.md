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

Built with Claude Code
