# VWAP Prediction System Documentation

## Overview

Welcome to the VWAP Prediction System documentation. This system provides real-time VWAP pattern detection and rate-based prediction for SSI HOSE BUSD data.

## Documentation Index

### 1. [Data Format](DATA_FORMAT.md)
**Comprehensive guide to SSI BUSD data format**

- Raw JSON structure from SSI WebSocket feed
- Field definitions and parsing rules
- VWAP calculation methodology
- Data quality filters and validation
- Trading session times and cutoff rules
- Output data format for predictions

**Read this first** if you want to understand the input data structure.

### 2. [Algorithm](ALGORITHM.md)
**Detailed explanation of detection and prediction algorithms**

- Pattern detection using sliding window
- Groupby logic: (stock, volume) tuples
- Rate-based linear extrapolation for predictions
- Timestamp-based replay mechanism
- Performance optimizations
- Configuration parameters

**Read this** to understand how the system works internally.

### 3. [Historical Comparison](HISTORICAL_COMPARISON.md)
**Comparison with iceberg_detector (historical version)**

- Architecture differences
- Feature comparison tables
- Key improvements in current system
- Why this approach is better for prediction
- When to use each system
- Migration guide

**Read this** to understand the evolution and design decisions.

## Quick Navigation

### For New Users
1. Start with the [main README](../README.md) for quick start
2. Read [Data Format](DATA_FORMAT.md) to understand the input
3. Read [Algorithm](ALGORITHM.md) to understand the processing
4. Optional: [Historical Comparison](HISTORICAL_COMPARISON.md) for context

### For Developers
1. [Algorithm](ALGORITHM.md) - Implementation details
2. [Data Format](DATA_FORMAT.md) - Data structures
3. Source code:
   - `vwap_prediction_backend.py` - Main streaming processor
   - `core/detector.py` - FastVWAPDetector
   - `core/predictor.py` - VWAPPredictor
   - `core/parser.py` - SSI BUSD parser

### For Researchers
1. [Historical Comparison](HISTORICAL_COMPARISON.md) - Evolution and design choices
2. [Algorithm](ALGORITHM.md) - Detection and prediction methodology
3. [Data Format](DATA_FORMAT.md) - Data specifications

## Key Concepts

### VWAP (Volume-Weighted Average Price)
Cumulative sum of (volume × price) / 1 billion, used to track institutional money flow.

### Pattern Detection
Identifying repetitive (stock, volume) tuples within a sliding window that indicate algorithmic execution.

### Rate-Based Prediction
Linear extrapolation: `prediction = current + (rate × horizon)` where rate is calculated from the last 2 data points.

### Timestamp-Based Replay
Preserving natural market timing while allowing configurable speed multipliers (1x - 100x).

## System Architecture

```
SSI BUSD Stream (stdin)
    ↓
Parser (core/parser.py)
    ↓
FastVWAPDetector (core/detector.py)
    ↓
VWAPPredictor (core/predictor.py)
    ↓
Ray Shared Memory
    ↓
Dash Dashboard (frontend)
```

## Configuration Quick Reference

```python
# Detection
window_seconds = 300          # 5-minute sliding window
min_occurrences = 5           # Minimum pattern repetitions
volume_threshold = 200        # Minimum shares

# Prediction
prediction_interval_sec = 15  # Every 15s (data time)
prediction_horizons = [15]    # 15 minutes ahead

# Replay
replay_speed_multiplier = 5.0 # 5x faster than real-time

# Dashboard
update_interval_ms = 200      # 200ms updates
```

## Common Use Cases

### Real-Time Monitoring
```bash
# Start backend at 5x speed
cat /d/data/ssi/ws/2025_11_27_ssi_hose_busd.received.txt | \
    python vwap_prediction_backend.py --speed 5.0

# Start dashboard
pm2 start ecosystem.config.js

# Access: http://localhost:8050
```

### Different Replay Speeds
```bash
# Normal speed (1x)
python vwap_prediction_backend.py --speed 1.0

# Fast replay (10x)
python vwap_prediction_backend.py --speed 10.0

# Very fast (50x)
python vwap_prediction_backend.py --speed 50.0
```

### Changing Days
Use the day selector in the dashboard to switch between available dates.

## Performance Characteristics

| Metric | Value |
|--------|-------|
| Parsing throughput | ~10,000 bubbles/sec |
| Detection throughput | ~5,000 bubbles/sec |
| Dashboard update rate | 5 Hz (200ms) |
| Replay speed range | 1x - 100x |
| Prediction interval | 15s (data time) |
| Prediction horizon | 15 minutes |

## Data Quality

### Filters Applied
- Only `MAIN` lot trades
- Volume ≥ 200 shares
- Time cutoff at 14:40:00
- Post-KRX data only (May 2024+)

### Timezone
- Raw data: UTC
- Display: Asia/Bangkok (UTC+7)
- HOSE trading hours: 09:00 - 14:30 (UTC+7)

## Troubleshooting

### Backend Not Processing
- Check tmux session: `tmux attach -t vwap-backend`
- Verify data file exists and is readable
- Check logs for errors

### Dashboard Not Updating
- Check PM2 status: `pm2 status`
- View logs: `pm2 logs vwap-frontend`
- Verify Ray is running: `ray status`

### Predictions Not Appearing
- Need at least 2 data points for rate calculation
- Check prediction interval (default: 15s data time)
- Verify data is after market open (09:00)

### Ray Connection Issues
```bash
# Restart Ray
conda run -n quantum ray stop
ray start --head
```

## Additional Resources

### External Documentation
- SSI WebSocket API
- HOSE trading regulations
- VN30 index composition (post-KRX)

### Related Projects
- `~/PycharmProjects/iceberg_detector` - Historical research system
- `~/quantum-trading-system` - Broader trading infrastructure

## Contributing

When adding new features or fixing bugs:
1. Update relevant documentation files
2. Add examples to this README if appropriate
3. Update configuration tables if parameters change
4. Test with multiple replay speeds
5. Verify predictions match expected formula

## Version History

- **Current**: Real-time prediction with timestamp-based replay
- **Historical**: iceberg_detector batch processing system

See [Historical Comparison](HISTORICAL_COMPARISON.md) for detailed evolution.

## Contact & Support

For issues or questions:
- Check documentation in this directory
- Review source code comments
- Consult historical iceberg_detector docs for background

---

**Last Updated**: 2025-11-28

Built with Claude Code
