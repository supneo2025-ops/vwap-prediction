#!/usr/bin/env python3
"""
Verify VWAP predictions match the formula:
prediction = current + (rate × 15)
where rate = (current - previous) / time_span_minutes
"""

import pandas as pd
from metis import gen_ray_functions

# Load data from Ray
_, _, psave, pload = gen_ray_functions()

df = pload('vwap_predictions')

if df is None or df.empty:
    print("No data available yet. Make sure backend is running.")
    exit(1)

print(f"Total rows: {len(df)}")
print(f"Columns: {df.columns.tolist()}")

# Prefer lunch-gap-adjusted timestamps if available
time_col = 'effective_timestamp' if 'effective_timestamp' in df.columns else 'timestamp'

# Check last few predictions
for i in range(max(0, len(df) - 5), len(df)):
    if i < 1:
        continue

    row = df.iloc[i]
    prev_row = df.iloc[i-1]

    # Calculate time span in minutes (using adjusted timestamps if available)
    time_span_ms = row[time_col] - prev_row[time_col]
    time_span_min = time_span_ms / (60 * 1000)

    # Calculate rates
    bu_rate = (row['bu_current'] - prev_row['bu_current']) / time_span_min
    sd_rate = (row['sd_current'] - prev_row['sd_current']) / time_span_min
    busd_rate = (row['busd_current'] - prev_row['busd_current']) / time_span_min

    # Expected predictions
    expected_bu = row['bu_current'] + (bu_rate * 15)
    expected_sd = row['sd_current'] + (sd_rate * 15)
    expected_busd = row['busd_current'] + (busd_rate * 15)

    # Actual predictions
    actual_bu = row.get('bu_pred_15min', 0)
    actual_sd = row.get('sd_pred_15min', 0)
    actual_busd = row.get('busd_pred_15min', 0)

    print(f"\nRow {i}:")
    print(f"  Time: {row['datetime']}")
    print(f"  Time span: {time_span_min:.2f} min")
    print(f"  BU current: {row['bu_current']:.2f}, rate: {bu_rate:.2f}/min")
    print(f"  BU expected: {expected_bu:.2f}, actual: {actual_bu:.2f}, diff: {abs(expected_bu - actual_bu):.2f}")
    print(f"  SD current: {row['sd_current']:.2f}, rate: {sd_rate:.2f}/min")
    print(f"  SD expected: {expected_sd:.2f}, actual: {actual_sd:.2f}, diff: {abs(expected_sd - actual_sd):.2f}")
    print(f"  BUSD current: {row['busd_current']:.2f}, rate: {busd_rate:.2f}/min")
    print(f"  BUSD expected: {expected_busd:.2f}, actual: {actual_busd:.2f}, diff: {abs(expected_busd - actual_busd):.2f}")

    # Check if predictions match (within small tolerance)
    tolerance = 0.01
    bu_match = abs(expected_bu - actual_bu) < tolerance
    sd_match = abs(expected_sd - actual_sd) < tolerance
    busd_match = abs(expected_busd - actual_busd) < tolerance

    if bu_match and sd_match and busd_match:
        print("  ✓ All predictions match!")
    else:
        print("  ✗ Predictions DO NOT match!")
