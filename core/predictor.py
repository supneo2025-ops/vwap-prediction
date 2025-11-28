"""
VWAP Predictor

Predicts future VWAP values based on current state and recent trends.
"""

from dataclasses import dataclass
from typing import List, Optional
import pandas as pd
from .detector import VWAPState


@dataclass
class VWAPPrediction:
    """
    VWAP prediction at a specific future timepoint.

    Attributes:
        timestamp: Current timestamp when prediction was made (milliseconds)
        prediction_horizon_min: How many minutes ahead this prediction is for
        bu_pred: Predicted BU VWAP in billions
        sd_pred: Predicted SD VWAP in billions
        busd_pred: Predicted net VWAP (BU - SD) in billions
    """
    timestamp: int
    prediction_horizon_min: int
    bu_pred: float
    sd_pred: float
    busd_pred: float


class VWAPPredictor:
    """
    Rate-Based VWAP Predictor.

    Calculates current VWAP accumulation rate and extrapolates into the future.

    Formula: prediction = current_vwap + (rate_per_minute * horizon_minutes)

    Where rate is calculated from recent historical data points.
    """

    def __init__(self, prediction_horizons: List[int] = None, rate_window_minutes: float = 1.0):
        """
        Initialize predictor.

        Args:
            prediction_horizons: List of prediction horizons in minutes
                                (default: [5, 15])
            rate_window_minutes: Time window for rate calculation in minutes
                               (default: 1.0, uses last 1 minute for current rate)
        """
        if prediction_horizons is None:
            prediction_horizons = [5, 15]

        self.prediction_horizons = sorted(prediction_horizons)
        self.rate_window_minutes = rate_window_minutes

    def predict(self, current_state: VWAPState, recent_history: Optional[List[dict]] = None) -> List[VWAPPrediction]:
        """
        Generate predictions for all configured horizons.

        Calculates VWAP accumulation rate from recent history and extrapolates.

        Args:
            current_state: Current VWAP state from detector
            recent_history: List of recent data points (dicts with timestamp, bu_current, sd_current, busd_current)
                          If None or insufficient data, defaults to zero rate

        Returns:
            List of VWAPPrediction objects, one per horizon
        """
        # Calculate rates from recent history
        bu_rate, sd_rate, busd_rate = self._calculate_rates(current_state, recent_history)

        predictions = []

        for horizon_min in self.prediction_horizons:
            # Extrapolate: prediction = current + (rate * horizon)
            prediction = VWAPPrediction(
                timestamp=current_state.timestamp,
                prediction_horizon_min=horizon_min,
                bu_pred=current_state.bu_vwap + (bu_rate * horizon_min),
                sd_pred=current_state.sd_vwap + (sd_rate * horizon_min),
                busd_pred=current_state.busd_vwap + (busd_rate * horizon_min)
            )
            predictions.append(prediction)

        return predictions

    def _calculate_rates(self, current_state: VWAPState, recent_history: Optional[List[dict]]) -> tuple:
        """
        Calculate VWAP accumulation rates (per minute) from recent history.

        Uses the last 2 data points to calculate the current instantaneous rate.
        This gives us the most recent trend.

        Args:
            current_state: Current VWAP state
            recent_history: Recent data points

        Returns:
            Tuple of (bu_rate, sd_rate, busd_rate) in billions per minute
        """
        if not recent_history or len(recent_history) < 2:
            # Not enough history, assume zero rate
            return 0.0, 0.0, 0.0

        # Use last 2 points for instantaneous rate
        # This captures the most recent trend
        last_point = recent_history[-1]
        prev_point = recent_history[-2]

        # Calculate time span in minutes
        time_span_ms = last_point['timestamp'] - prev_point['timestamp']
        time_span_min = time_span_ms / (60 * 1000)

        if time_span_min == 0:
            return 0.0, 0.0, 0.0

        # Calculate VWAP change between last two points
        bu_change = last_point['bu_current'] - prev_point['bu_current']
        sd_change = last_point['sd_current'] - prev_point['sd_current']
        busd_change = last_point['busd_current'] - prev_point['busd_current']

        # Calculate rates (change per minute)
        bu_rate = bu_change / time_span_min
        sd_rate = sd_change / time_span_min
        busd_rate = busd_change / time_span_min

        return bu_rate, sd_rate, busd_rate

    def predict_single(self, current_state: VWAPState, horizon_min: int) -> VWAPPrediction:
        """
        Generate prediction for a single horizon.

        Args:
            current_state: Current VWAP state from detector
            horizon_min: Prediction horizon in minutes

        Returns:
            VWAPPrediction object
        """
        return VWAPPrediction(
            timestamp=current_state.timestamp,
            prediction_horizon_min=horizon_min,
            bu_pred=current_state.bu_vwap,
            sd_pred=current_state.sd_vwap,
            busd_pred=current_state.busd_vwap
        )
