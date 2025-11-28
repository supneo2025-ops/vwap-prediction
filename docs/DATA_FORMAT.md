# Data Format Documentation

## Overview

This document describes the SSI HOSE BUSD data format used in the VWAP prediction system. The data comes from the SSI WebSocket feed for the Ho Chi Minh Stock Exchange (HOSE), specifically the aggregated trade (BUSD) stream.

## Data Source

**Location**: `/d/data/ssi/ws/`
**File Pattern**: `YYYY_MM_DD_ssi_hose_busd.received.txt`
**Format**: Line-delimited JSON
**Time Period**: May 2025 - November 2025 (post-KRX integration)
**Timezone**: UTC (converted to UTC+7 for display)

### Example Files
```
/d/data/ssi/ws/2025_11_27_ssi_hose_busd.received.txt
/d/data/ssi/ws/2025_05_15_ssi_hose_busd.received.txt
```

## Raw Data Format

### JSON Structure

Each line in the data file is a complete JSON message from the SSI WebSocket stream:

```json
{
  "channel": "X:HOSE:BUSD",
  "data": {
    "response": {
      "payloadData": "MAIN|L#VCB|85.2|1000|0|0|0|bu|0|1|0|5|1732675200123",
      "messageType": "BUSD",
      "timestamp": 1732675200000
    }
  }
}
```

### Payload Data Fields

The `payloadData` field contains pipe-delimited values:

| Position | Field Name | Type | Description | Example |
|----------|------------|------|-------------|---------|
| 0 | Lot Type | string | Always "MAIN" for main lot trades | MAIN |
| 1 | Stock Symbol | string | Stock code with "L#" prefix | L#VCB |
| 2 | Price | float | Execution price | 85.2 |
| 3 | Volume | int | Trade volume in shares | 1000 |
| 4-6 | Reserved | - | Reserved fields (not used) | 0 |
| 7 | Matched By | string | Trade initiator: "bu" or "sd" | bu |
| 8-11 | Reserved | - | Reserved fields (not used) | 0,1,0,5 |
| 12 | Server Time | int64 | HOSE exchange timestamp (ms) | 1732675200123 |

### Field Definitions

#### Stock Symbol
- **Raw Format**: `L#VCB`, `L#FPT`, `L#HPG`
- **Processed Format**: `VCB`, `FPT`, `HPG` (strip "L#" prefix)
- **Type**: String
- **Examples**: VCB (Vietcombank), FPT (FPT Corporation), HPG (Hoa Phat Group)

#### Price
- **Unit**: Vietnamese Dong (VND) per share
- **Type**: Float
- **Precision**: Varies by stock (typically 0.1 or 1.0)
- **Example**: 85.2 means 85,200 VND per share

#### Volume
- **Unit**: Number of shares
- **Type**: Integer
- **Minimum**: Typically >150 for institutional interest
- **Example**: 1000 shares

#### Matched By
- **Values**:
  - `bu`: Buy Up (trade matched at ask/higher price, bullish)
  - `sd`: Sell Down (trade matched at bid/lower price, bearish)
- **Type**: String (lowercase)
- **Meaning**: Indicates which side was the aggressor

#### Server Time (serverTime)
- **Unit**: Milliseconds since Unix epoch
- **Type**: int64
- **Source**: HOSE exchange official timestamp
- **Timezone**: UTC
- **Display**: Converted to Asia/Bangkok (UTC+7)
- **Example**: 1732675200123 = 2025-11-27 09:00:00.123 UTC+7
- **Requirement**: Parser drops messages that do not contain `serverTime`, so pre-KRX data (April 2025 and earlier) cannot be processed

## Parsed Data Structure

### Bubble Class

After parsing, each trade becomes a `Bubble` object:

```python
@dataclass
class Bubble:
    stock: str          # Stock symbol (L# prefix stripped)
    volume: int         # Trade volume in shares
    price: float        # Execution price in VND
    timestamp: int      # serverTime in milliseconds
    matched_by: str     # 'bu' or 'sd'
```

### Example
```python
Bubble(
    stock='VCB',
    volume=1000,
    price=85.2,
    timestamp=1732675200123,
    matched_by='bu'
)
```

## VWAP Calculation

### Formula

VWAP (Volume-Weighted Average Price) is calculated as cumulative sum of:

```
VWAP = Σ(volume × price) / 1,000,000,000
```

### Components

- **BU VWAP**: Cumulative sum for Buy Up trades only
- **SD VWAP**: Cumulative sum for Sell Down trades only
- **BUSD VWAP**: Net flow = BU VWAP - SD VWAP

### Unit Explanation

The division by 1 billion (1e9) converts the raw value to billions of VND, making it more readable:

```python
# Example:
# Trade: 1000 shares @ 85.2 VND = 85,200 VND total value
# VWAP contribution: (1000 × 85.2) / 1e9 = 0.0000852 billion VND

# After many trades, BU VWAP might be: 150.75 billion VND
```

### Accumulation

VWAP is accumulated only when a pattern is detected:

```python
if is_vwap_pattern:
    vwap_value = (volume × price) / 1e9
    bu_vwap_cumsum += vwap_value  # For 'bu' trades
    sd_vwap_cumsum += vwap_value  # For 'sd' trades
```

## Pattern Detection Criteria

### Volume Threshold
- **Default**: 200 shares
- **Reason**: Filter out small retail trades
- **Configuration**: Adjustable in detector settings

### Time Window
- **Default**: 300 seconds (5 minutes)
- **Purpose**: Sliding window for pattern detection
- **Configuration**: `window_seconds` parameter

### Minimum Occurrences
- **Default**: 5 repetitions
- **Purpose**: Confirm algorithmic pattern
- **Configuration**: `min_occurrences` parameter

### Pattern Key
Patterns are identified by the tuple:
```python
pattern_key = (stock, volume)
```

Example: `('VCB', 1000)` represents all 1000-share trades of VCB stock

## Data Quality

### Filtering Rules

1. **Lot Type Filter**
   - Only process `MAIN` lot trades
   - Skip odd-lot and other special lot types

2. **Time Cutoff**
   - Ignore data after 14:40:00 (2:40 PM)
   - Reason: Avoid post-market noise and closing volatility

3. **Volume Filter**
   - Skip trades below volume threshold
   - Default: 200 shares minimum

### Data Validation

```python
def parse_ssi_busd_line(line: str) -> Optional[Bubble]:
    # Parse JSON
    msg = json.loads(line.strip())

    # Extract payload
    payload_data = msg.get('data', {}).get('response', {}).get('payloadData')
    fields = payload_data.split('|')

    # Filter: Only MAIN lot
    if fields[0] != 'MAIN':
        return None

    # Extract fields
    return Bubble(
        stock=fields[1].replace('L#', ''),  # Strip prefix
        volume=int(fields[3]),
        price=float(fields[2]),
        timestamp=int(fields[12]),          # serverTime
        matched_by=fields[7]                # 'bu' or 'sd'
    )
```

## Trading Session Times

Vietnam stock market (HOSE) operates in UTC+7 timezone:

| Session | Time (UTC+7) | Description |
|---------|--------------|-------------|
| Pre-open | 08:45 - 09:00 | Order collection |
| Opening | 09:00 - 09:15 | Opening auction |
| Morning | 09:15 - 11:30 | Continuous trading |
| Break | 11:30 - 13:00 | Lunch break (no trading) |
| Afternoon | 13:00 - 14:30 | Continuous trading |
| Close | 14:30 - 14:45 | Closing auction |

**Data Processing Cutoff**: 14:40:00 to avoid post-close noise

## Historical Context

### KRX Integration
- **Date**: 2025-05-05 onwards
- **Impact**: Changed VN30 index structure
- **Data**: Only use post-KRX data for consistency

### Data Availability
- **Range**: May 2025 - November 2025 (post-KRX serverTime data only)
- **Coverage**: All HOSE trading days
- **Quality**: Production-grade SSI WebSocket feed

## Performance Characteristics

### Data Volume
- **Typical Day**: 50,000 - 200,000 trades
- **Peak Days**: Up to 500,000 trades
- **File Size**: 10-50 MB per day (text)

### Processing Speed
- **Parsing**: ~10,000 trades/second
- **Detection**: ~5,000 trades/second
- **Replay**: Configurable (1x - 100x speed)

## Usage Example

### Reading Data
```python
# Read from file
with open('/d/data/ssi/ws/2025_11_27_ssi_hose_busd.received.txt', 'r') as f:
    for line in f:
        bubble = parse_ssi_busd_line(line)
        if bubble:
            detector.add_bubble(bubble)
```

### Streaming Replay
```bash
# Replay at 5x speed
cat /d/data/ssi/ws/2025_11_27_ssi_hose_busd.received.txt | \
    python vwap_prediction_backend.py --speed 5.0
```

## Output Data Format

### Timeseries Data
The system produces DataFrame output with these columns:

| Column | Type | Description |
|--------|------|-------------|
| timestamp | int64 | Data timestamp (ms) |
| datetime | datetime64[ns, UTC+7] | Display timestamp |
| bu_current | float | Current BU VWAP |
| sd_current | float | Current SD VWAP |
| busd_current | float | Current BUSD net flow |
| bu_pred_15min | float | BU prediction 15 min ahead |
| sd_pred_15min | float | SD prediction 15 min ahead |
| busd_pred_15min | float | BUSD prediction 15 min ahead |
| pred_datetime_15min | datetime64[ns, UTC+7] | Prediction target time |

### Current Rates
Separate DataFrame tracking instantaneous rates:

| Column | Type | Description |
|--------|------|-------------|
| timestamp | int64 | Data timestamp (ms) |
| bu_rate | float | BU rate (per minute) |
| sd_rate | float | SD rate (per minute) |
| busd_rate | float | BUSD rate (per minute) |

## References

- SSI WebSocket API documentation
- HOSE trading rules and regulations
- VN30 index post-KRX composition
