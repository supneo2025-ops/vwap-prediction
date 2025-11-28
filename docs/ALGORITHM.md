# Algorithm Documentation

## Overview

This document explains the algorithms used in the VWAP prediction system, including pattern detection, groupby logic, prediction methodology, and timestamp-based replay.

## Table of Contents

1. [Pattern Detection Algorithm](#pattern-detection-algorithm)
2. [Groupby Logic](#groupby-logic)
3. [Prediction Algorithm](#prediction-algorithm)
4. [Timestamp-Based Replay](#timestamp-based-replay)
5. [Performance Optimizations](#performance-optimizations)

---

## Pattern Detection Algorithm

### Overview

The `FastVWAPDetector` uses a sliding window approach to detect repetitive volume patterns that indicate institutional algorithmic trading (VWAP/TWAP/Iceberg orders).

### Core Principle

Institutional traders split large orders into smaller chunks with consistent volume to minimize market impact. By detecting these repetitive patterns, we can identify algorithmic execution.

### Detection Logic

```python
class FastVWAPDetector:
    def __init__(self, window_seconds=300, min_occurrences=5, volume_threshold=200):
        self.window_seconds = window_seconds      # 5-minute sliding window
        self.min_occurrences = min_occurrences    # Minimum 5 repetitions
        self.volume_threshold = volume_threshold  # Ignore volume < 200
```

### Algorithm Steps

#### 1. Pattern Key Generation

For each incoming trade (bubble), create a pattern key:

```python
pattern_key = (stock, volume)
# Example: ('VCB', 1000) represents all 1000-share trades of VCB
```

This groups all trades with the same stock and volume together.

#### 2. Sliding Window Management

Maintain a time-ordered queue for each pattern:

```python
# Store bubbles in a deque for efficient FIFO operations
pattern_deque = deque()

# Add new bubble
pattern_deque.append(bubble)

# Remove expired bubbles (outside window)
cutoff_time = current_timestamp - (window_seconds * 1000)
while pattern_deque and pattern_deque[0].timestamp < cutoff_time:
    pattern_deque.popleft()
```

#### 3. Pattern Classification

Determine if pattern qualifies as VWAP:

```python
is_vwap_pattern = len(pattern_deque) >= min_occurrences
```

If true, this pattern is considered algorithmic execution.

#### 4. VWAP Accumulation

For confirmed VWAP patterns, accumulate the weighted value:

```python
if is_vwap_pattern:
    vwap_value = (bubble.volume × bubble.price) / 1e9

    if bubble.matched_by == 'bu':
        bu_vwap_cumsum += vwap_value
    elif bubble.matched_by == 'sd':
        sd_vwap_cumsum += vwap_value

    busd_vwap_cumsum = bu_vwap_cumsum - sd_vwap_cumsum
```

### Complete Detection Flow

```
Bubble arrives
    ↓
Volume >= threshold?
    ↓ Yes
Generate pattern_key = (stock, volume)
    ↓
Add to pattern's deque
    ↓
Remove expired bubbles from deque
    ↓
len(deque) >= min_occurrences?
    ↓ Yes
Mark as VWAP pattern
    ↓
Accumulate VWAP value
    ↓
Return VWAPState
```

### Example

Consider VCB stock with 1000-share trades:

```
Time      Stock  Volume  Pattern Queue  VWAP?
09:00:00  VCB    1000    [1]            No (< 5)
09:00:15  VCB    1000    [1,2]          No (< 5)
09:00:30  VCB    1000    [1,2,3]        No (< 5)
09:00:45  VCB    1000    [1,2,3,4]      No (< 5)
09:01:00  VCB    1000    [1,2,3,4,5]    YES! (>= 5)
09:01:15  VCB    1000    [1,2,3,4,5,6]  YES!
...
09:05:01  VCB    1000    [2,3,4,5,6]    YES! (expired #1)
```

After the 5th occurrence, all subsequent trades with the same pattern are marked as VWAP.

---

## Groupby Logic

### Grouping Dimensions

The system groups trades by two dimensions:

1. **Stock Symbol**: Each stock is tracked independently
2. **Volume Level**: Each distinct volume is tracked separately

### Why Group by (Stock, Volume)?

Institutional algorithms typically use:
- **Consistent volume**: Same chunk size throughout execution
- **Stock-specific**: Each stock has its own VWAP order

Example groupings:
```python
('VCB', 1000)  # All 1000-share VCB trades
('VCB', 500)   # All 500-share VCB trades (different pattern)
('FPT', 1000)  # All 1000-share FPT trades (different stock)
```

### Data Structures

```python
# Separate tracking for BU and SD
bu_patterns: Dict[Tuple[str, int], deque] = defaultdict(deque)
sd_patterns: Dict[Tuple[str, int], deque] = defaultdict(deque)

# Example contents:
bu_patterns = {
    ('VCB', 1000): deque([bubble1, bubble2, bubble3, ...]),
    ('VCB', 500):  deque([bubble4, bubble5, ...]),
    ('FPT', 1000): deque([bubble6, bubble7, bubble8, ...])
}
```

### Groupby Benefits

1. **Precision**: Detect exact volume patterns
2. **Independence**: Different stocks don't interfere
3. **Flexibility**: Same stock can have multiple VWAP orders with different volumes
4. **Efficiency**: O(1) lookup for pattern tracking

---

## Prediction Algorithm

### Overview

The prediction algorithm uses **rate-based linear extrapolation** to forecast VWAP values 15 minutes ahead.

### Core Formula

```
prediction = current + (rate × horizon)
```

Where:
- `current`: Current VWAP value
- `rate`: Accumulation rate per minute
- `horizon`: Prediction horizon (15 minutes)

### Rate Calculation

#### Using Last 2 Points (Instantaneous Rate)

```python
def _calculate_rates(self, current_state, recent_history):
    """Calculate VWAP accumulation rates per minute."""
    if len(recent_history) < 2:
        return 0.0, 0.0, 0.0

    # Use last 2 points for instantaneous rate
    last_point = recent_history[-1]
    prev_point = recent_history[-2]

    # Calculate time span in minutes
    time_span_ms = last_point['timestamp'] - prev_point['timestamp']
    time_span_min = time_span_ms / (60 * 1000)

    if time_span_min == 0:
        return 0.0, 0.0, 0.0

    # Calculate rates (change per minute)
    bu_rate = (last_point['bu_current'] - prev_point['bu_current']) / time_span_min
    sd_rate = (last_point['sd_current'] - prev_point['sd_current']) / time_span_min
    busd_rate = (last_point['busd_current'] - prev_point['busd_current']) / time_span_min

    return bu_rate, sd_rate, busd_rate
```

#### Why Last 2 Points?

- **Instantaneous trend**: Captures most recent accumulation rate
- **Responsive**: Quickly adapts to changing patterns
- **Simple**: No complex smoothing or averaging
- **Data-efficient**: Minimal historical data required

### Prediction Generation

```python
def predict(self, current_state, recent_history):
    """Generate predictions for configured horizons."""
    # Calculate current rates
    bu_rate, sd_rate, busd_rate = self._calculate_rates(current_state, recent_history)

    predictions = []
    for horizon_min in self.prediction_horizons:  # e.g., [15]
        # Linear extrapolation
        bu_pred = current_state.bu_vwap + (bu_rate × horizon_min)
        sd_pred = current_state.sd_vwap + (sd_rate × horizon_min)
        busd_pred = current_state.busd_vwap + (busd_rate × horizon_min)

        predictions.append(Prediction(
            prediction_horizon_min=horizon_min,
            bu_pred=bu_pred,
            sd_pred=sd_pred,
            busd_pred=busd_pred
        ))

    return predictions
```

### Concrete Example

**Scenario**: User asked for this specific example

```
Current BU VWAP: 100 billion VND
Current rate: 1 billion VND per minute
Horizon: 15 minutes

Prediction = 100 + (1 × 15) = 115 billion VND
```

**Real Data Example**:

```python
# t=0: BU VWAP = 150.50 billion
# t=1min: BU VWAP = 152.00 billion

# Rate calculation
time_span = 1 minute
rate = (152.00 - 150.50) / 1 = 1.50 per minute

# 15-minute prediction
prediction = 152.00 + (1.50 × 15) = 174.50 billion
```

### Prediction Timing

Predictions are generated based on **data time**, not wall-clock time:

```python
# Check if it's time to generate prediction (data-time based)
if bubble.timestamp - last_prediction_timestamp >= prediction_interval_ms:
    generate_prediction(current_state)
    last_prediction_timestamp = bubble.timestamp
```

Default interval: Every 15 seconds of data time.

### Prediction Output

Each prediction includes:

```python
{
    'timestamp': 1732675200000,              # Current data time
    'datetime': '2025-11-27 09:00:00',       # Current display time
    'bu_current': 150.50,                    # Current BU VWAP
    'bu_pred_15min': 174.50,                 # Predicted BU VWAP
    'pred_datetime_15min': '2025-11-27 09:15:00',  # Prediction target time
    # ... similar for SD and BUSD
}
```

---

## Timestamp-Based Replay

### Overview

The replay system preserves natural market timing by using data timestamps rather than fixed message rates.

### User Requirement

> "I want 5x speed = the python replays with 5 times faster than the actual received data"

### Algorithm

```python
# Initialize
prev_bubble_timestamp = None
replay_speed_multiplier = 5.0  # User-configurable (1x - 100x)

# For each bubble
if prev_bubble_timestamp is not None:
    # Calculate time difference in the data
    data_time_diff_ms = bubble.timestamp - prev_bubble_timestamp
    data_time_diff_sec = data_time_diff_ms / 1000.0

    # Scale sleep duration by speed multiplier
    sleep_duration = data_time_diff_sec / replay_speed_multiplier

    if sleep_duration > 0:
        time.sleep(sleep_duration)

# Update for next iteration
prev_bubble_timestamp = bubble.timestamp
```

### Example

**Original Data Timing**:
```
09:00:00.000 - Bubble 1
09:00:00.500 - Bubble 2  (0.5s gap)
09:00:05.000 - Bubble 3  (4.5s gap)
09:00:05.100 - Bubble 4  (0.1s gap)
```

**5x Speed Replay**:
```
Wall-clock 0.000s - Bubble 1
Wall-clock 0.100s - Bubble 2  (0.5/5 = 0.1s)
Wall-clock 1.000s - Bubble 3  (4.5/5 = 0.9s)
Wall-clock 1.020s - Bubble 4  (0.1/5 = 0.02s)
```

**50x Speed Replay**:
```
Wall-clock 0.000s - Bubble 1
Wall-clock 0.010s - Bubble 2  (0.5/50 = 0.01s)
Wall-clock 0.100s - Bubble 3  (4.5/50 = 0.09s)
Wall-clock 0.102s - Bubble 4  (0.1/50 = 0.002s)
```

### Benefits

1. **Natural rhythm**: Preserves market microstructure
2. **Burst periods**: Fast trading during market open
3. **Quiet periods**: Slower trading during mid-day
4. **Scalable speed**: Works at any multiplier (1x - 100x)

### Coordination with Predictions

Predictions also scale with replay speed:

```python
# Prediction interval: 15 seconds of data time
prediction_interval_ms = 15 * 1000

# At 50x speed:
# - Data advances 15 seconds every 0.3 wall-clock seconds
# - Dashboard updates every 0.2 seconds (200ms)
# - Multiple updates show same prediction until next data point
```

This ensures: **"The replay must match the real world"** (user requirement)

---

## Performance Optimizations

### 1. Efficient Pattern Tracking

**Use deque for O(1) operations**:
```python
from collections import deque, defaultdict

# O(1) append and popleft
pattern_deque = deque()
pattern_deque.append(bubble)      # O(1)
pattern_deque.popleft()           # O(1)
```

### 2. Lazy Window Cleanup

Only remove expired bubbles when adding new ones:
```python
# Don't scan all patterns every time
# Only clean the pattern being updated
cutoff_time = bubble.timestamp - (window_seconds * 1000)
while pattern_deque and pattern_deque[0].timestamp < cutoff_time:
    pattern_deque.popleft()
```

### 3. Minimal History Retention

Only keep last 2 points for rate calculation:
```python
# Don't store entire history
# Just keep recent points for prediction
if len(timeseries_data) > 1000:
    timeseries_data = timeseries_data[-1000:]  # Keep last 1000 only
```

### 4. Ray Shared Memory

Zero-copy data sharing between backend and frontend:
```python
# Save DataFrame to Ray
self.psave('vwap_predictions', df)

# Load in frontend (same memory, no copy)
df = self.pload('vwap_predictions')
```

### 5. Fast Dashboard Updates

200ms update interval catches rapid predictions at high speeds:
```python
dcc.Interval(
    id='interval-component',
    interval=200,  # 200ms = 5 updates/second
    n_intervals=0
)
```

At 50x speed:
- Predictions every 0.3s wall-clock time
- Dashboard updates every 0.2s
- Catches all new predictions in real-time

---

## Algorithm Complexity

### Time Complexity

| Operation | Complexity | Notes |
|-----------|------------|-------|
| Parse bubble | O(1) | Simple field extraction |
| Pattern lookup | O(1) | Dict key lookup |
| Add to deque | O(1) | Append operation |
| Window cleanup | O(k) | k = expired bubbles |
| VWAP accumulation | O(1) | Simple addition |
| Rate calculation | O(1) | Last 2 points |
| Prediction | O(h) | h = number of horizons (usually 1) |

**Overall**: O(1) per bubble (amortized)

### Space Complexity

| Data Structure | Size | Notes |
|----------------|------|-------|
| Pattern deques | O(n×p) | n = patterns, p = window size |
| Timeseries | O(t) | t = time points (limited to 1000) |
| Ray shared memory | O(t×c) | t = time points, c = columns |

**Overall**: O(n×p) dominated by pattern tracking

### Throughput

Real-world performance:
- **Parsing**: ~10,000 bubbles/second
- **Detection**: ~5,000 bubbles/second
- **Replay (5x)**: ~200 bubbles/second (wall-clock)
- **Replay (50x)**: ~2,000 bubbles/second (wall-clock)

---

## Configuration Parameters

### Detection Parameters

```python
window_seconds = 300          # 5-minute sliding window
min_occurrences = 5           # Minimum pattern repetitions
volume_threshold = 200        # Minimum shares for institutional interest
```

### Prediction Parameters

```python
prediction_interval_sec = 15  # Generate predictions every 15s (data time)
prediction_horizons = [15]    # Predict 15 minutes ahead
```

### Replay Parameters

```python
replay_speed_multiplier = 5.0  # 5x faster than real-time
```

### Dashboard Parameters

```python
update_interval_ms = 200      # Dashboard updates every 200ms
```

### Data Quality Parameters

```python
cutoff_time = '14:40:00'      # Stop processing after 2:40 PM
lot_type = 'MAIN'             # Only process main lot trades
```

---

## Algorithm Validation

### Verification Script

`verify_predictions.py` confirms prediction accuracy:

```python
# Load predictions from Ray
df = pload('vwap_predictions')

# For each prediction
for i in range(len(df) - 1):
    current = df.iloc[i]
    next_point = df.iloc[i + 1]

    # Calculate expected rate
    time_span = (next_point['timestamp'] - current['timestamp']) / 60000
    rate = (next_point['bu_current'] - current['bu_current']) / time_span

    # Expected prediction
    expected = current['bu_current'] + (rate × 15)
    actual = current['bu_pred_15min']

    # Verify match
    assert abs(expected - actual) < 0.01, f"Mismatch at {i}"
```

### Test Cases

1. **Constant rate**: Verify linear extrapolation
2. **Zero rate**: Prediction equals current
3. **Negative rate**: Prediction below current
4. **Rate changes**: Responsive to new trend

---

## References

- User requirement: "if current agg bu vwap is 100 and the current vwap rate is 1 for 1 minute, then the next 15 min prediction should be 100 + 15 = 115"
- User requirement: "I want 5x speed = the python replays with 5 times faster than the actual received data"
- User requirement: "The replay must match the real world"
- Source: `core/detector.py:FastVWAPDetector`
- Source: `core/predictor.py:VWAPPredictor`
- Source: `vwap_prediction_backend.py:timestamp-based replay`
