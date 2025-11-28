#!/usr/bin/env python3
"""
VWAP Prediction Frontend

Dash-based real-time visualization dashboard for VWAP predictions.
Reads data from Ray shared memory and displays interactive charts.

Usage:
    python vwap_prediction_frontend.py
    # Then open http://localhost:8050 in browser
"""

import sys
import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from dash import Dash, dcc, html
from dash.dependencies import Input, Output, State
import logging
import subprocess
import os
from pathlib import Path
from glob import glob

from metis import gen_ray_functions

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Ray shared memory
_, _, psave, pload = gen_ray_functions()

# Backend control
data_dir = Path("/d/data/ssi/ws")
python_bin = "/Users/m2/anaconda3/envs/quantum/bin/python"
backend_script = Path(__file__).parent / "vwap_prediction_backend.py"
tmux_session = "vwap-backend"


def get_available_days():
    """Get list of available trading days"""
    files = list(data_dir.glob("*_ssi_hose_busd.received.txt"))
    days = []
    for f in files:
        # Extract date from filename: YYYY_MM_DD_ssi_hose_busd.received.txt
        parts = f.stem.split('_')
        if len(parts) >= 3:
            date_str = f"{parts[0]}-{parts[1]}-{parts[2]}"
            days.append(date_str)
    return sorted(days, reverse=True)  # Most recent first


def restart_backend(day: str, speed: float):
    """Restart backend with new settings using tmux"""
    logger.info(f"Restarting backend: day={day}, speed={speed}x")

    # Convert day format: YYYY-MM-DD -> YYYY_MM_DD
    day_file = day.replace('-', '_')
    data_file = data_dir / f"{day_file}_ssi_hose_busd.received.txt"

    if not data_file.exists():
        logger.error(f"Data file not found: {data_file}")
        return False

    try:
        # Send Ctrl+C to stop current process in tmux
        subprocess.run(
            f"tmux send-keys -t {tmux_session} C-c",
            shell=True,
            check=False
        )

        # Wait for process to stop
        import time
        time.sleep(1)

        # Send new command to tmux
        cmd = f"cat {data_file} | {python_bin} {backend_script} --speed {speed}"
        subprocess.run(
            f"tmux send-keys -t {tmux_session} '{cmd}' C-m",
            shell=True,
            check=True
        )

        logger.info(f"Backend restarted in tmux session '{tmux_session}'")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to restart backend: {e}")
        return False


# Create Dash app
app = Dash(__name__)
app.title = "VWAP Prediction Dashboard"

# Get available days for dropdown
available_days = get_available_days()

# App layout
app.layout = html.Div([
    html.H1("VWAP Prediction Dashboard", style={'textAlign': 'center', 'color': '#2c3e50', 'marginBottom': '20px'}),

    # Controls Panel
    html.Div([
        html.H3("Dashboard Controls", style={'color': '#34495e', 'marginBottom': '15px'}),
        html.Div([
            # Day selector
            html.Div([
                html.Label("Trading Day:", style={'fontWeight': 'bold', 'marginRight': '10px'}),
                dcc.Dropdown(
                    id='day-selector',
                    options=[{'label': day, 'value': day} for day in available_days],
                    value=available_days[0] if available_days else None,
                    style={'width': '200px', 'display': 'inline-block'}
                )
            ], style={'display': 'inline-block', 'marginRight': '30px'}),

            # Speed selector
            html.Div([
                html.Label("Replay Speed:", style={'fontWeight': 'bold', 'marginRight': '10px'}),
                dcc.Slider(
                    id='speed-input',
                    min=1,
                    max=100,
                    step=1,
                    value=5,
                    marks={
                        1: '1x',
                        5: '5x',
                        10: '10x',
                        25: '25x',
                        50: '50x',
                        100: '100x'
                    },
                    tooltip={"placement": "bottom", "always_visible": True}
                ),
                html.Div(id='speed-display', style={'marginTop': '5px', 'fontSize': '14px', 'fontWeight': 'bold', 'color': '#2980b9'})
            ], style={'display': 'inline-block', 'marginRight': '30px', 'width': '300px'}),

            # Update button
            html.Button(
                'Update Dashboard',
                id='update-button',
                n_clicks=0,
                style={
                    'backgroundColor': '#3498db',
                    'color': 'white',
                    'border': 'none',
                    'padding': '10px 20px',
                    'borderRadius': '5px',
                    'cursor': 'pointer',
                    'fontSize': '14px',
                    'fontWeight': 'bold'
                }
            ),

            # Status message
            html.Div(id='update-status', style={'display': 'inline-block', 'marginLeft': '20px', 'color': '#27ae60', 'fontWeight': 'bold'})
        ], style={'display': 'flex', 'alignItems': 'center'})
    ], style={'padding': '15px', 'backgroundColor': '#ecf0f1', 'borderRadius': '5px', 'margin': '10px'}),

    # Live Statistics
    html.Div([
        html.H3("Live Statistics", style={'color': '#34495e'}),
        html.Div(id='stats-display', style={'fontSize': '14px', 'fontFamily': 'monospace'})
    ], style={'padding': '10px', 'backgroundColor': '#ecf0f1', 'borderRadius': '5px', 'margin': '10px'}),

    # BU VWAP Chart
    html.Div([
        html.H3("BU VWAP - Actual vs 15-Min Prediction", style={'color': '#34495e', 'marginTop': '20px'}),
        dcc.Graph(id='bu-vwap-chart', style={'height': '400px'}),
    ], style={'padding': '10px'}),

    # SD VWAP Chart
    html.Div([
        html.H3("SD VWAP - Actual vs 15-Min Prediction", style={'color': '#34495e', 'marginTop': '20px'}),
        dcc.Graph(id='sd-vwap-chart', style={'height': '400px'}),
    ], style={'padding': '10px'}),

    # BUSD VWAP Chart
    html.Div([
        html.H3("BUSD VWAP (BU - SD) - Actual vs 15-Min Prediction", style={'color': '#34495e', 'marginTop': '20px'}),
        dcc.Graph(id='busd-vwap-chart', style={'height': '400px'}),
    ], style={'padding': '10px'}),

    # Legend
    html.Div([
        html.P("Chart Legend:", style={'fontSize': '12px', 'color': '#7f8c8d', 'fontWeight': 'bold'}),
        html.Ul([
            html.Li("Solid line: Current detected VWAP", style={'color': '#3498db'}),
            html.Li("Dashed line: 15-minute prediction (extends into future)", style={'color': '#e74c3c'}),
        ], style={'fontSize': '12px', 'color': '#7f8c8d'})
    ], style={'padding': '20px', 'backgroundColor': '#ecf0f1', 'borderRadius': '5px', 'margin': '20px'}),

    # Auto-refresh component - updates every 200ms (fast enough for up to 75x speed)
    # At 50x speed: 15s data time = 0.3s wall-clock, so 200ms catches 1-2 updates
    # At 100x speed: 15s data time = 0.15s wall-clock, close to 200ms
    dcc.Interval(
        id='interval-component',
        interval=200,  # 200 milliseconds = 0.2 seconds
        n_intervals=0
    )
], style={'fontFamily': 'Arial, sans-serif', 'backgroundColor': '#f8f9fa', 'padding': '20px'})


def load_data():
    """
    Load VWAP prediction data from Ray shared memory.

    Returns:
        DataFrame or None if data not available.
    """
    try:
        df = pload('vwap_predictions')
        if df is None or df.empty:
            return None
        return df
    except Exception as e:
        logger.warning(f"Error loading data from Ray shared memory: {e}")
        return None


def load_rates():
    """
    Load current VWAP rates from Ray shared memory.

    Returns:
        DataFrame or None if data not available.
    """
    try:
        rates_df = pload('vwap_current_rates')
        if rates_df is None or rates_df.empty:
            return None
        return rates_df
    except Exception as e:
        return None


@app.callback(
    Output('speed-display', 'children'),
    Input('speed-input', 'value')
)
def update_speed_display(speed):
    """Update speed display"""
    if speed is None:
        return "Speed: 5x"
    return f"Speed: {speed}x"


@app.callback(
    Output('update-status', 'children'),
    Input('update-button', 'n_clicks'),
    State('day-selector', 'value'),
    State('speed-input', 'value'),
    prevent_initial_call=True
)
def handle_update(n_clicks, day, speed):
    """Handle update button click - restart backend with new settings"""
    logger.info(f"UPDATE BUTTON CLICKED: n_clicks={n_clicks}, day={day}, speed={speed}, speed_type={type(speed)}")

    # Default speed if not provided
    if speed is None or speed == '':
        speed = 5
        logger.info(f"Speed was None, defaulting to {speed}")

    if n_clicks > 0 and day:
        try:
            speed = float(speed)
            logger.info(f"Calling restart_backend with day={day}, speed={speed}")
            success = restart_backend(day, speed)
            if success:
                logger.info("Backend restarted successfully")
                return f"✓ Updated to {day} at {speed}x speed"
            else:
                logger.error("Backend restart failed")
                return f"✗ Error updating backend"
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid speed value: {speed}, error: {e}")
            return f"✗ Invalid speed value"

    logger.warning(f"Conditions not met: n_clicks={n_clicks}, day={day}, speed={speed}")
    return ""


@app.callback(
    Output('stats-display', 'children'),
    Input('interval-component', 'n_intervals')
)
def update_stats(n):
    """Update live statistics display."""
    df = load_data()
    rates_df = load_rates()

    if df is None or df.empty:
        return html.Div([
            html.P("⏳ Waiting for data from backend...", style={'color': '#e67e22', 'fontSize': '16px'}),
            html.P("Make sure the backend is running and processing data.", style={'color': '#95a5a6'})
        ])

    # Calculate statistics
    last_row = df.iloc[-1]
    total_rows = len(df)

    # Get latest values
    bu_current = last_row['bu_current']
    sd_current = last_row['sd_current']
    busd_current = last_row['busd_current']
    bu_pred_15min = last_row.get('bu_pred_15min', 0)
    sd_pred_15min = last_row.get('sd_pred_15min', 0)
    busd_pred_15min = last_row.get('busd_pred_15min', 0)

    # Get current rates
    bu_rate = 0.0
    sd_rate = 0.0
    busd_rate = 0.0
    if rates_df is not None and not rates_df.empty:
        rate_row = rates_df.iloc[-1]
        bu_rate = rate_row.get('bu_rate', 0.0)
        sd_rate = rate_row.get('sd_rate', 0.0)
        busd_rate = rate_row.get('busd_rate', 0.0)

    stats_content = [
        html.Div([
            html.Span("📊 Total Data Points: ", style={'fontWeight': 'bold'}),
            html.Span(f"{total_rows:,}", style={'color': '#27ae60'})
        ]),
        html.Div([
            html.Span("🕒 Latest Time: ", style={'fontWeight': 'bold'}),
            html.Span(str(last_row['datetime']), style={'color': '#2980b9'})
        ]),
        html.Div([
            html.Span("🔵 BU VWAP: ", style={'fontWeight': 'bold'}),
            html.Span(f"{bu_current:.2f} B", style={'color': '#3498db', 'fontSize': '16px'}),
            html.Span(f" → {bu_pred_15min:.2f} B (15min)", style={'color': '#95a5a6', 'fontSize': '14px'}),
            html.Span(f" | Rate: {bu_rate:+.2f} B/min", style={'color': '#7f8c8d', 'fontSize': '12px', 'marginLeft': '10px'})
        ]),
        html.Div([
            html.Span("🔴 SD VWAP: ", style={'fontWeight': 'bold'}),
            html.Span(f"{sd_current:.2f} B", style={'color': '#e74c3c', 'fontSize': '16px'}),
            html.Span(f" → {sd_pred_15min:.2f} B (15min)", style={'color': '#95a5a6', 'fontSize': '14px'}),
            html.Span(f" | Rate: {sd_rate:+.2f} B/min", style={'color': '#7f8c8d', 'fontSize': '12px', 'marginLeft': '10px'})
        ]),
        html.Div([
            html.Span("💹 BUSD VWAP: ", style={'fontWeight': 'bold'}),
            html.Span(f"{busd_current:.2f} B", style={'color': '#9b59b6', 'fontSize': '16px'}),
            html.Span(f" → {busd_pred_15min:.2f} B (15min)", style={'color': '#95a5a6', 'fontSize': '14px'}),
            html.Span(f" | Rate: {busd_rate:+.2f} B/min", style={'color': '#7f8c8d', 'fontSize': '12px', 'marginLeft': '10px'})
        ]),
    ]

    return html.Div(stats_content, style={'lineHeight': '2'})


def create_vwap_chart(df, vwap_type, color_actual, color_pred, title):
    """
    Create a VWAP chart with actual and predicted values.

    Args:
        df: DataFrame with VWAP data
        vwap_type: 'bu', 'sd', or 'busd'
        color_actual: Color for actual line
        color_pred: Color for prediction line
        title: Chart title

    Returns:
        Plotly figure
    """
    if df is None or df.empty:
        return {
            'data': [],
            'layout': go.Layout(
                title='Waiting for data...',
                xaxis={'title': 'Time'},
                yaxis={'title': 'VWAP (Billions)'},
                hovermode='x unified'
            )
        }

    # Get full day range from data
    if 'datetime' in df.columns:
        x_actual = df['datetime']
        # Set x-axis range for full trading day (9:00 - 15:00)
        first_datetime = pd.to_datetime(df['datetime'].iloc[0])
        day_start = first_datetime.replace(hour=9, minute=0, second=0, microsecond=0)
        day_end = first_datetime.replace(hour=15, minute=0, second=0, microsecond=0)
    else:
        x_actual = df['timestamp']
        day_start = None
        day_end = None

    # Actual VWAP values
    y_actual = df[f'{vwap_type}_current']

    # Prediction values (15 min)
    pred_col = f'{vwap_type}_pred_15min'
    pred_time_col = 'pred_datetime_15min'

    if pred_col in df.columns and pred_time_col in df.columns:
        x_pred = df[pred_time_col]
        y_pred = df[pred_col]
    else:
        x_pred = None
        y_pred = None

    # Create traces
    traces = []

    # Actual VWAP line (solid)
    traces.append(go.Scatter(
        x=x_actual,
        y=y_actual,
        mode='lines',
        name=f'Actual {vwap_type.upper()}',
        line=dict(color=color_actual, width=2),
        hovertemplate=f'<b>Actual</b><br>Time: %{{x}}<br>{vwap_type.upper()}: %{{y:.2f}}B<extra></extra>'
    ))

    # Prediction line (dashed, extends into future)
    if x_pred is not None and y_pred is not None:
        traces.append(go.Scatter(
            x=x_pred,
            y=y_pred,
            mode='lines',
            name=f'15-min Prediction',
            line=dict(color=color_pred, width=2, dash='dash'),
            hovertemplate=f'<b>15-min Pred</b><br>Time: %{{x}}<br>{vwap_type.upper()}: %{{y:.2f}}B<extra></extra>'
        ))

    # Create layout
    layout = go.Layout(
        title=title,
        xaxis={
            'title': 'Time (UTC+7)',
            'showgrid': True,
            'gridcolor': '#e1e8ed',
            'range': [day_start, day_end] if day_start and day_end else None
        },
        yaxis={
            'title': 'VWAP (Billions)',
            'showgrid': True,
            'gridcolor': '#e1e8ed'
        },
        hovermode='x unified',
        plot_bgcolor='#ffffff',
        paper_bgcolor='#f8f9fa',
        font=dict(family='Arial, sans-serif', size=12),
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1
        ),
        margin=dict(l=60, r=40, t=60, b=60)
    )

    return {
        'data': traces,
        'layout': layout
    }


@app.callback(
    Output('bu-vwap-chart', 'figure'),
    Input('interval-component', 'n_intervals')
)
def update_bu_chart(n):
    """Update BU VWAP chart."""
    df = load_data()
    return create_vwap_chart(df, 'bu', '#3498db', '#e74c3c', 'BU VWAP: Actual vs 15-Min Prediction')


@app.callback(
    Output('sd-vwap-chart', 'figure'),
    Input('interval-component', 'n_intervals')
)
def update_sd_chart(n):
    """Update SD VWAP chart."""
    df = load_data()
    return create_vwap_chart(df, 'sd', '#e74c3c', '#3498db', 'SD VWAP: Actual vs 15-Min Prediction')


@app.callback(
    Output('busd-vwap-chart', 'figure'),
    Input('interval-component', 'n_intervals')
)
def update_busd_chart(n):
    """Update BUSD VWAP chart."""
    df = load_data()
    return create_vwap_chart(df, 'busd', '#9b59b6', '#f39c12', 'BUSD VWAP: Actual vs 15-Min Prediction')


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("VWAP Prediction Frontend Starting...")
    logger.info("=" * 60)
    logger.info("Dashboard will be available at: http://localhost:8050")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 60)

    # Run Dash app
    app.run(
        debug=False,
        host='0.0.0.0',
        port=8050
    )


if __name__ == '__main__':
    main()
