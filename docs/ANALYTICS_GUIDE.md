# Analytics Guide

This guide explains how to use the VWAP Prediction System for data analysis and research.

## Table of Contents
1. [Quick Start](#quick-start)
2. [GUI-Based Control (No Manual tmux Required)](#gui-based-control)
3. [Accessing Data Programmatically](#accessing-data-programmatically)
4. [Analytics Workflows](#analytics-workflows)
5. [Example Analysis Scripts](#example-analysis-scripts)
6. [Tips & Best Practices](#tips--best-practices)

---

## Quick Start

### 1. Launch the Dashboard

```bash
# Start the frontend (PM2 recommended for auto-restart)
pm2 start ecosystem.config.js

# Or run directly
python vwap_prediction_frontend.py
```

Access dashboard at: **http://localhost:8050**

### 2. Start a Replay Session

**You don't need to work with tmux manually!** The dashboard GUI controls everything:

1. Open http://localhost:8050 in your browser
2. Use the **Trading Day** dropdown to select a date (only post-KRX data: May 2025+)
3. Adjust **Replay Speed** slider (1x to 100x)
4. Click **Update Dashboard** button

The frontend automatically:
- Stops any running backend process in tmux
- Starts a new replay with your selected settings
- Streams data to Ray shared memory for real-time analysis

---

## GUI-Based Control (No Manual tmux Required)

### Dashboard Controls

The web interface provides complete control over the backend replay:

| Control | Purpose | Notes |
|---------|---------|-------|
| **Trading Day** dropdown | Select which day to replay | Only shows post-KRX data (May 2025+) |
| **Replay Speed** slider | Control playback speed | 1x = real-time, 100x = fast-forward |
| **Update Dashboard** button | Apply changes and restart backend | Automatically manages tmux session |

### How It Works

When you click "Update Dashboard":

```python
# The frontend does this automatically:
1. Sends Ctrl+C to tmux session 'vwap-backend'
2. Waits for the previous process to stop
3. Sends new command: cat <data_file> | python vwap_prediction_backend.py --speed <X>
4. New replay starts immediately
```

**Location in code**: `vwap_prediction_frontend.py:62` (`restart_backend()` function)

### Behind the Scenes

The system uses a dedicated tmux session named `vwap-backend`:

```bash
# You can still check the backend status manually if needed:
tmux ls  # List all sessions
tmux attach -t vwap-backend  # View backend logs (Ctrl+B, D to detach)
```

But **you don't need to do this** for normal analytics work - the GUI handles everything!

---

## Accessing Data Programmatically

All VWAP data is stored in **Ray shared memory** for high-performance access.

### Data Structure

The system stores a pandas DataFrame in Ray with key: `'vwap_predictions'`

**Columns:**
- `timestamp` - Original HOSE market timestamp (milliseconds)
- `effective_timestamp` - Lunch-gap-adjusted timestamp for smooth rate calculations
- `datetime` - Human-readable timestamp (Asia/Bangkok timezone)
- `bu_current` - Current BU VWAP (billions)
- `sd_current` - Current SD VWAP (billions)
- `busd_current` - Current BUSD VWAP (billions)
- `bu_pred_15min` - 15-minute BU prediction
- `sd_pred_15min` - 15-minute SD prediction
- `busd_pred_15min` - 15-minute BUSD prediction
- `pred_datetime_15min` - Predicted datetime (15 min ahead)

### Basic Access Pattern

```python
#!/usr/bin/env python3
"""
Example: Load and analyze VWAP data from Ray
"""
import pandas as pd
from metis import gen_ray_functions

# Initialize Ray functions
_, _, psave, pload = gen_ray_functions()

# Load current VWAP data
df = pload('vwap_predictions')

if df is None or df.empty:
    print("No data available. Make sure backend is running.")
    exit(1)

print(f"Loaded {len(df)} data points")
print(f"Time range: {df['datetime'].min()} to {df['datetime'].max()}")
print(df.head())
```

### Real-Time Updates

Data updates every **15 seconds** (data time, not wall-clock time):

```python
import time
from metis import gen_ray_functions

_, _, psave, pload = gen_ray_functions()

print("Monitoring live VWAP data...")
prev_count = 0

while True:
    df = pload('vwap_predictions')
    if df is not None:
        current_count = len(df)
        if current_count > prev_count:
            last_row = df.iloc[-1]
            print(f"[{last_row['datetime']}] "
                  f"BU: {last_row['bu_current']:.2f}B, "
                  f"SD: {last_row['sd_current']:.2f}B, "
                  f"BUSD: {last_row['busd_current']:.2f}B")
            prev_count = current_count

    time.sleep(0.5)  # Check every 500ms
```

---

## Analytics Workflows

### Workflow 1: Historical Comparison

Compare VWAP patterns across multiple trading days:

```python
#!/usr/bin/env python3
"""
Compare VWAP patterns across different days
"""
import pandas as pd
from pathlib import Path
from core.parser import parse_ssi_busd_line
from core.detector import VWAPDetector

# Analyze multiple days
days = ['2025-05-15', '2025-06-20', '2025-11-27']
results = {}

for day in days:
    day_file = day.replace('-', '_')
    data_file = Path(f"/d/data/ssi/ws/{day_file}_ssi_hose_busd.received.txt")

    if not data_file.exists():
        continue

    detector = VWAPDetector(window_seconds=300)

    with open(data_file, 'r') as f:
        for line in f:
            bubble = parse_ssi_busd_line(line)
            if bubble:
                detector.add_bubble(bubble)

    results[day] = detector.get_state()
    print(f"{day}: BU={results[day].bu_vwap:.2f}B, "
          f"SD={results[day].sd_vwap:.2f}B, "
          f"BUSD={results[day].busd_vwap:.2f}B")
```

### Workflow 2: Rate Analysis

Analyze VWAP change rates over time:

```python
#!/usr/bin/env python3
"""
Analyze VWAP rate patterns
"""
import pandas as pd
import matplotlib.pyplot as plt
from metis import gen_ray_functions

_, _, psave, pload = gen_ray_functions()
df = pload('vwap_predictions')

if df is None or df.empty:
    print("No data available")
    exit(1)

# Calculate rates between consecutive points
time_col = 'effective_timestamp'  # Use lunch-gap-adjusted time
df['time_diff_min'] = df[time_col].diff() / (60 * 1000)
df['bu_rate'] = df['bu_current'].diff() / df['time_diff_min']
df['sd_rate'] = df['sd_current'].diff() / df['time_diff_min']
df['busd_rate'] = df['busd_current'].diff() / df['time_diff_min']

# Statistical summary
print("Rate Statistics (B/min):")
print(df[['bu_rate', 'sd_rate', 'busd_rate']].describe())

# Plot rate distributions
fig, axes = plt.subplots(1, 3, figsize=(15, 4))
df['bu_rate'].hist(bins=50, ax=axes[0], color='blue', alpha=0.7)
axes[0].set_title('BU Rate Distribution')
axes[0].set_xlabel('B/min')

df['sd_rate'].hist(bins=50, ax=axes[1], color='red', alpha=0.7)
axes[1].set_title('SD Rate Distribution')
axes[1].set_xlabel('B/min')

df['busd_rate'].hist(bins=50, ax=axes[2], color='purple', alpha=0.7)
axes[2].set_title('BUSD Rate Distribution')
axes[2].set_xlabel('B/min')

plt.tight_layout()
plt.savefig('vwap_rate_analysis.png', dpi=150)
print("Saved: vwap_rate_analysis.png")
```

### Workflow 3: Prediction Accuracy

Evaluate prediction accuracy:

```python
#!/usr/bin/env python3
"""
Analyze prediction accuracy by comparing predicted vs actual values
"""
import pandas as pd
from metis import gen_ray_functions

_, _, psave, pload = gen_ray_functions()
df = pload('vwap_predictions')

if df is None or df.empty or len(df) < 60:
    print("Not enough data for accuracy analysis")
    exit(1)

# For each prediction made 15 minutes ago, check against current actual
# Find rows that are ~15 minutes apart
errors = []

for i in range(len(df) - 1):
    pred_time = df.iloc[i]['pred_datetime_15min']

    # Find closest actual datapoint to predicted time
    time_diffs = abs(df['datetime'] - pred_time)
    closest_idx = time_diffs.idxmin()

    if time_diffs[closest_idx] < pd.Timedelta(minutes=2):  # Within 2 min tolerance
        predicted_bu = df.iloc[i]['bu_pred_15min']
        actual_bu = df.iloc[closest_idx]['bu_current']

        predicted_sd = df.iloc[i]['sd_pred_15min']
        actual_sd = df.iloc[closest_idx]['sd_current']

        predicted_busd = df.iloc[i]['busd_pred_15min']
        actual_busd = df.iloc[closest_idx]['busd_current']

        errors.append({
            'pred_time': pred_time,
            'bu_error': abs(predicted_bu - actual_bu),
            'sd_error': abs(predicted_sd - actual_sd),
            'busd_error': abs(predicted_busd - actual_busd),
            'bu_pct_error': abs(predicted_bu - actual_bu) / actual_bu * 100 if actual_bu != 0 else 0,
            'sd_pct_error': abs(predicted_sd - actual_sd) / actual_sd * 100 if actual_sd != 0 else 0,
            'busd_pct_error': abs(predicted_busd - actual_busd) / abs(actual_busd) * 100 if actual_busd != 0 else 0,
        })

if errors:
    error_df = pd.DataFrame(errors)
    print("Prediction Accuracy Analysis:")
    print(f"Total predictions evaluated: {len(error_df)}")
    print("\nMean Absolute Error (B):")
    print(f"  BU:   {error_df['bu_error'].mean():.2f}")
    print(f"  SD:   {error_df['sd_error'].mean():.2f}")
    print(f"  BUSD: {error_df['busd_error'].mean():.2f}")
    print("\nMean Percentage Error (%):")
    print(f"  BU:   {error_df['bu_pct_error'].mean():.2f}%")
    print(f"  SD:   {error_df['sd_pct_error'].mean():.2f}%")
    print(f"  BUSD: {error_df['busd_pct_error'].mean():.2f}%")
else:
    print("No matching predictions found")
```

### Workflow 4: Export for External Analysis

Export data to various formats:

```python
#!/usr/bin/env python3
"""
Export VWAP data for analysis in other tools
"""
import pandas as pd
from metis import gen_ray_functions

_, _, psave, pload = gen_ray_functions()
df = pload('vwap_predictions')

if df is None or df.empty:
    print("No data available")
    exit(1)

# Export to CSV
df.to_csv('vwap_data.csv', index=False)
print(f"Exported {len(df)} rows to vwap_data.csv")

# Export to Excel with multiple sheets
with pd.ExcelWriter('vwap_analysis.xlsx', engine='openpyxl') as writer:
    df.to_excel(writer, sheet_name='Raw Data', index=False)

    # Summary statistics
    summary = df[['bu_current', 'sd_current', 'busd_current']].describe()
    summary.to_excel(writer, sheet_name='Statistics')

    # Latest predictions
    latest = df.tail(20)[['datetime', 'bu_current', 'bu_pred_15min',
                          'sd_current', 'sd_pred_15min',
                          'busd_current', 'busd_pred_15min']]
    latest.to_excel(writer, sheet_name='Latest Predictions', index=False)

print("Exported to vwap_analysis.xlsx")

# Export to JSON for web apps
df.to_json('vwap_data.json', orient='records', date_format='iso')
print("Exported to vwap_data.json")

# Export to Parquet for efficient storage
df.to_parquet('vwap_data.parquet', index=False)
print("Exported to vwap_data.parquet")
```

---

## Example Analysis Scripts

### Complete Analysis Example

Here's a complete script that demonstrates multiple analytics techniques:

```python
#!/usr/bin/env python3
"""
Comprehensive VWAP Analytics Example
"""
import pandas as pd
import numpy as np
from metis import gen_ray_functions
import matplotlib.pyplot as plt
import seaborn as sns

# Load data
_, _, psave, pload = gen_ray_functions()
df = pload('vwap_predictions')

if df is None or df.empty:
    print("No data available. Start a replay first!")
    exit(1)

print(f"Analyzing {len(df)} VWAP data points")
print(f"Time range: {df['datetime'].min()} to {df['datetime'].max()}\n")

# 1. Basic Statistics
print("="*60)
print("BASIC STATISTICS")
print("="*60)
print(df[['bu_current', 'sd_current', 'busd_current']].describe())

# 2. Rate Analysis
time_col = 'effective_timestamp'
df['time_diff_min'] = df[time_col].diff() / (60 * 1000)
df['bu_rate'] = df['bu_current'].diff() / df['time_diff_min']
df['sd_rate'] = df['sd_current'].diff() / df['time_diff_min']
df['busd_rate'] = df['busd_current'].diff() / df['time_diff_min']

print("\n" + "="*60)
print("RATE STATISTICS (B/min)")
print("="*60)
print(df[['bu_rate', 'sd_rate', 'busd_rate']].describe())

# 3. Correlation Analysis
print("\n" + "="*60)
print("CORRELATION MATRIX")
print("="*60)
corr = df[['bu_current', 'sd_current', 'busd_current',
           'bu_rate', 'sd_rate', 'busd_rate']].corr()
print(corr)

# 4. Time-of-Day Patterns
df['hour'] = df['datetime'].dt.hour
df['minute'] = df['datetime'].dt.minute

hourly_stats = df.groupby('hour').agg({
    'bu_current': ['mean', 'std'],
    'sd_current': ['mean', 'std'],
    'busd_current': ['mean', 'std']
})

print("\n" + "="*60)
print("HOURLY PATTERNS")
print("="*60)
print(hourly_stats)

# 5. Volatility Analysis
window = 10  # 10-point rolling window
df['bu_volatility'] = df['bu_current'].rolling(window).std()
df['sd_volatility'] = df['sd_current'].rolling(window).std()
df['busd_volatility'] = df['busd_current'].rolling(window).std()

print("\n" + "="*60)
print("VOLATILITY STATISTICS (rolling std)")
print("="*60)
print(df[['bu_volatility', 'sd_volatility', 'busd_volatility']].describe())

# 6. Generate Visualizations
plt.style.use('seaborn-v0_8-darkgrid')
fig, axes = plt.subplots(3, 2, figsize=(16, 12))

# VWAP trends
df.plot(x='datetime', y='bu_current', ax=axes[0,0], color='blue', legend=False)
axes[0,0].set_title('BU VWAP Over Time')
axes[0,0].set_ylabel('Billions')

df.plot(x='datetime', y='sd_current', ax=axes[1,0], color='red', legend=False)
axes[1,0].set_title('SD VWAP Over Time')
axes[1,0].set_ylabel('Billions')

df.plot(x='datetime', y='busd_current', ax=axes[2,0], color='purple', legend=False)
axes[2,0].set_title('BUSD VWAP Over Time')
axes[2,0].set_ylabel('Billions')

# Rate distributions
df['bu_rate'].hist(bins=50, ax=axes[0,1], color='blue', alpha=0.7)
axes[0,1].set_title('BU Rate Distribution')
axes[0,1].set_xlabel('B/min')

df['sd_rate'].hist(bins=50, ax=axes[1,1], color='red', alpha=0.7)
axes[1,1].set_title('SD Rate Distribution')
axes[1,1].set_xlabel('B/min')

df['busd_rate'].hist(bins=50, ax=axes[2,1], color='purple', alpha=0.7)
axes[2,1].set_title('BUSD Rate Distribution')
axes[2,1].set_xlabel('B/min')

plt.tight_layout()
plt.savefig('vwap_comprehensive_analysis.png', dpi=150, bbox_inches='tight')
print("\n✓ Saved visualization: vwap_comprehensive_analysis.png")

# 7. Export processed data
output_df = df[['datetime', 'bu_current', 'sd_current', 'busd_current',
                'bu_rate', 'sd_rate', 'busd_rate',
                'bu_volatility', 'sd_volatility', 'busd_volatility',
                'bu_pred_15min', 'sd_pred_15min', 'busd_pred_15min']]
output_df.to_csv('vwap_processed.csv', index=False)
print("✓ Saved processed data: vwap_processed.csv")

print("\n" + "="*60)
print("ANALYSIS COMPLETE")
print("="*60)
```

Save this as `analyze_vwap.py` and run:
```bash
python analyze_vwap.py
```

---

## Tips & Best Practices

### 1. Data Collection

**Use Fast Replay for Data Collection:**
```bash
# Fast replay (100x) to quickly build historical dataset
# Then use GUI to set speed to 100x and click Update
```

**Monitor Progress:**
```python
# Check how much data has been collected
from metis import gen_ray_functions
_, _, psave, pload = gen_ray_functions()
df = pload('vwap_predictions')
print(f"Collected {len(df)} data points")
print(f"Latest time: {df['datetime'].max()}")
```

### 2. Timing Considerations

**Understand the Two Timestamp Columns:**
- `timestamp` - Original HOSE market time (includes lunch gap 11:30-13:00)
- `effective_timestamp` - Lunch-gap-compressed time (smooth for rate calculations)

**For rate calculations, use `effective_timestamp`:**
```python
time_col = 'effective_timestamp' if 'effective_timestamp' in df.columns else 'timestamp'
df['time_diff_min'] = df[time_col].diff() / (60 * 1000)
df['rate'] = df['value'].diff() / df['time_diff_min']
```

### 3. Data Quality

**Check for Data Availability:**
```python
# Only post-KRX data (May 2025+) is supported
from pathlib import Path
data_dir = Path("/d/data/ssi/ws")
files = sorted(data_dir.glob("*_ssi_hose_busd.received.txt"))

for f in files:
    parts = f.stem.split('_')
    if len(parts) >= 3:
        year, month = int(parts[0]), int(parts[1])
        if year > 2025 or (year == 2025 and month >= 5):
            print(f"✓ {f.stem}")  # Available
        else:
            print(f"✗ {f.stem} (pre-KRX, lacks serverTime)")
```

### 4. Memory Management

**Clear Ray Memory Between Sessions:**
```python
from metis import gen_ray_functions
_, _, psave, pload = gen_ray_functions()

# Clear old data
psave('vwap_predictions', None)
print("Ray memory cleared")
```

### 5. Parallel Analysis

**Run Multiple Analyses in Parallel:**

You can have multiple Python scripts reading from Ray simultaneously:

```bash
# Terminal 1: Real-time monitoring
python monitor_live.py

# Terminal 2: Export data periodically
python export_hourly.py

# Terminal 3: Run custom analysis
python my_analysis.py
```

All will read the same shared Ray data without conflicts.

### 6. Debugging

**Verify Predictions:**
```bash
# Use the included verification script
python verify_predictions.py
```

**Check Backend Logs:**
```bash
# Attach to tmux to see backend output
tmux attach -t vwap-backend

# Detach with: Ctrl+B, then D
```

### 7. Performance Optimization

**For Large-Scale Analysis:**

```python
# Use chunking for processing large datasets
chunk_size = 10000
for i in range(0, len(df), chunk_size):
    chunk = df.iloc[i:i+chunk_size]
    process_chunk(chunk)
```

**Use Parquet for Storage:**
```python
# Much faster than CSV for large datasets
df.to_parquet('vwap_data.parquet')
df = pd.read_parquet('vwap_data.parquet')
```

---

## Additional Resources

- **Algorithm Details**: See [ALGORITHM.md](ALGORITHM.md)
- **Data Format Specification**: See [DATA_FORMAT.md](DATA_FORMAT.md)
- **Historical Comparisons**: See [HISTORICAL_COMPARISON.md](HISTORICAL_COMPARISON.md)
- **System Overview**: See [README.md](README.md)

---

**Questions or Issues?**

Check the main README or inspect the code:
- Frontend GUI controls: `vwap_prediction_frontend.py:62`
- Backend replay engine: `vwap_prediction_backend.py`
- Data parser: `core/parser.py`
- VWAP detector: `core/detector.py`

Built with Claude Code
