#!/usr/bin/env python3
"""
VWAP Prediction Backend

Streaming processor that reads SSI BUSD data from stdin,
detects VWAP patterns, generates predictions, and saves
results to Ray shared memory for frontend visualization.

Usage:
    cat /d/data/ssi/ws/2024_05_*_ssi_hose_busd.received.txt | python vwap_prediction_backend.py
"""

import sys
import time
import pandas as pd
from datetime import datetime
from typing import List
import logging
import argparse

from metis import gen_ray_functions
from core import parse_ssi_busd_line, FastVWAPDetector, VWAPPredictor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VWAPPredictionBackend:
    """
    Streaming VWAP detection and prediction backend.

    Processes SSI BUSD data from stdin, detects VWAP patterns,
    generates predictions, and publishes to Arrow shared memory.
    """

    def __init__(
        self,
        window_seconds: int = 300,
        min_occurrences: int = 5,
        volume_threshold: int = 200,
        prediction_interval_sec: int = 10,
        prediction_horizons: List[int] = None,
        replay_speed_multiplier: float = 1.0
    ):
        """
        Initialize backend.

        Args:
            window_seconds: VWAP detection window (default 300s)
            min_occurrences: Minimum pattern repetitions (default 5)
            volume_threshold: Minimum volume to consider (default 200)
            prediction_interval_sec: How often to generate predictions (default 10s)
            prediction_horizons: Prediction horizons in minutes (default [5, 15])
            replay_speed_multiplier: Replay speed multiplier (default 1.0 = real-time, 5.0 = 5x faster)
        """
        # Initialize detector
        self.detector = FastVWAPDetector(
            window_seconds=window_seconds,
            min_occurrences=min_occurrences,
            volume_threshold=volume_threshold
        )

        # Initialize predictor
        if prediction_horizons is None:
            prediction_horizons = [5, 15]
        self.predictor = VWAPPredictor(prediction_horizons=prediction_horizons)

        # Prediction settings (based on data time, not wall-clock time)
        self.prediction_interval_ms = prediction_interval_sec * 1000  # Convert to milliseconds
        self.last_prediction_data_timestamp = 0  # Track data timestamp, not wall-clock

        # Replay speed control - timestamp-based
        self.replay_speed_multiplier = replay_speed_multiplier
        self.prev_bubble_timestamp = None
        self.replay_start_wallclock = None
        self.replay_start_data_timestamp = None

        # Ray shared memory
        _, _, self.psave, self.pload = gen_ray_functions()

        # Data buffer for building timeseries
        self.timeseries_data = []

        # Current rates (for display)
        self.current_rates = {
            'bu_rate': 0.0,
            'sd_rate': 0.0,
            'busd_rate': 0.0,
            'timestamp': 0
        }

        # Statistics
        self.bubbles_processed = 0
        self.predictions_generated = 0
        self.start_time = time.time()

        logger.info("VWAP Prediction Backend initialized")
        logger.info(f"  Detection window: {window_seconds}s")
        logger.info(f"  Min occurrences: {min_occurrences}")
        logger.info(f"  Volume threshold: {volume_threshold}")
        logger.info(f"  Prediction interval: {prediction_interval_sec}s")
        logger.info(f"  Prediction horizons: {prediction_horizons} min")
        logger.info(f"  Replay speed: {replay_speed_multiplier}x (timestamp-based)")

    def process_line(self, line: str) -> bool:
        """
        Process a single line from stdin.

        Args:
            line: JSON string from SSI stream

        Returns:
            True if processed successfully, False otherwise
        """
        # Parse bubble
        bubble = parse_ssi_busd_line(line)
        if bubble is None:
            return False

        # Ignore data after 14:40:00 (2:40 PM)
        # Convert timestamp to datetime and check time
        bubble_dt = pd.to_datetime(bubble.timestamp, unit='ms', utc=True).tz_convert('Asia/Bangkok')
        if bubble_dt.hour >= 14 and bubble_dt.minute >= 40:
            if not hasattr(self, '_cutoff_logged'):
                logger.info(f"Reached cutoff time 14:40:00 at {bubble_dt}, stopping data processing")
                self._cutoff_logged = True
            return False

        # Add to detector and get current state
        current_state = self.detector.add_bubble(bubble)

        # Update statistics
        self.bubbles_processed += 1

        # Timestamp-based replay speed control
        if self.prev_bubble_timestamp is not None:
            # Calculate time difference in the data
            data_time_diff_ms = bubble.timestamp - self.prev_bubble_timestamp
            data_time_diff_sec = data_time_diff_ms / 1000.0

            # Calculate how long to sleep (scaled by speed multiplier)
            sleep_duration = data_time_diff_sec / self.replay_speed_multiplier

            if sleep_duration > 0:
                time.sleep(sleep_duration)

        # Update previous timestamp
        self.prev_bubble_timestamp = bubble.timestamp

        # Check if it's time to generate prediction (based on data time, not wall-clock)
        if bubble.timestamp - self.last_prediction_data_timestamp >= self.prediction_interval_ms:
            self._generate_and_save_prediction(current_state)
            self.last_prediction_data_timestamp = bubble.timestamp

        # Log progress periodically
        if self.bubbles_processed % 1000 == 0:
            elapsed = time.time() - self.start_time
            rate = self.bubbles_processed / elapsed if elapsed > 0 else 0
            logger.info(
                f"Processed {self.bubbles_processed} bubbles, "
                f"{self.predictions_generated} predictions, "
                f"{rate:.1f} bubbles/sec"
            )

        return True

    def _generate_and_save_prediction(self, current_state):
        """
        Generate predictions and save to Ray shared memory.

        Args:
            current_state: Current VWAPState from detector
        """
        # Build current data row
        current_row = {
            'timestamp': current_state.timestamp,
            'bu_current': current_state.bu_vwap,
            'sd_current': current_state.sd_vwap,
            'busd_current': current_state.busd_vwap,
        }

        # Create history including current state for rate calculation
        history_with_current = self.timeseries_data + [current_row]

        # Generate predictions with history INCLUDING current state
        predictions = self.predictor.predict(current_state, recent_history=history_with_current)

        # Calculate and save current rates for display
        if len(history_with_current) >= 2:
            last_point = history_with_current[-1]
            prev_point = history_with_current[-2]
            time_span_ms = last_point['timestamp'] - prev_point['timestamp']
            time_span_min = time_span_ms / (60 * 1000)

            if time_span_min > 0:
                self.current_rates['bu_rate'] = (last_point['bu_current'] - prev_point['bu_current']) / time_span_min
                self.current_rates['sd_rate'] = (last_point['sd_current'] - prev_point['sd_current']) / time_span_min
                self.current_rates['busd_rate'] = (last_point['busd_current'] - prev_point['busd_current']) / time_span_min
                self.current_rates['timestamp'] = current_state.timestamp

        # Build full data row with UTC+7 timezone
        row_data = {
            'timestamp': current_state.timestamp,
            'datetime': pd.to_datetime(current_state.timestamp, unit='ms', utc=True).tz_convert('Asia/Bangkok'),
            'bu_current': current_state.bu_vwap,
            'sd_current': current_state.sd_vwap,
            'busd_current': current_state.busd_vwap,
        }

        # Add predictions and prediction time (future timestamp)
        for pred in predictions:
            horizon = pred.prediction_horizon_min
            row_data[f'bu_pred_{horizon}min'] = pred.bu_pred
            row_data[f'sd_pred_{horizon}min'] = pred.sd_pred
            row_data[f'busd_pred_{horizon}min'] = pred.busd_pred
            # Add prediction datetime (15 minutes into future)
            pred_timestamp = current_state.timestamp + (horizon * 60 * 1000)  # Convert minutes to ms
            row_data[f'pred_datetime_{horizon}min'] = pd.to_datetime(pred_timestamp, unit='ms', utc=True).tz_convert('Asia/Bangkok')

        # Append to timeseries
        self.timeseries_data.append(row_data)

        # Convert to DataFrame
        df = pd.DataFrame(self.timeseries_data)

        # Save to Ray shared memory
        try:
            self.psave('vwap_predictions', df)
            # Also save current rates
            rates_df = pd.DataFrame([self.current_rates])
            self.psave('vwap_current_rates', rates_df)

            self.predictions_generated += 1

            if self.predictions_generated % 10 == 0:
                logger.debug(
                    f"Saved prediction #{self.predictions_generated}: "
                    f"BUSD={current_state.busd_vwap:.2f}B, "
                    f"rows={len(df)}"
                )
        except Exception as e:
            logger.error(f"Error saving to Ray shared memory: {e}")

    def run(self):
        """
        Main processing loop - read from stdin until EOF.
        """
        logger.info("Starting to read from stdin...")
        logger.info("Press Ctrl+C to stop")

        try:
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue

                self.process_line(line)

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
        finally:
            # Print final statistics
            elapsed = time.time() - self.start_time
            logger.info("=" * 60)
            logger.info("Backend Statistics:")
            logger.info(f"  Bubbles processed: {self.bubbles_processed}")
            logger.info(f"  Predictions generated: {self.predictions_generated}")
            logger.info(f"  Runtime: {elapsed:.1f}s")
            logger.info(f"  Processing rate: {self.bubbles_processed/elapsed:.1f} bubbles/sec")
            logger.info("=" * 60)


def main():
    """Main entry point."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='VWAP Prediction Backend')
    parser.add_argument('--speed', type=float, default=5.0,
                       help='Replay speed multiplier (default: 5.0)')
    args = parser.parse_args()

    # Create and run backend
    backend = VWAPPredictionBackend(
        window_seconds=300,               # 5-minute detection window
        min_occurrences=5,                # Minimum 5 pattern repetitions
        volume_threshold=200,             # Ignore volume < 200
        prediction_interval_sec=15,       # Generate predictions every 15 seconds
        prediction_horizons=[15],         # Predict 15 minutes ahead only
        replay_speed_multiplier=args.speed  # Replay speed from command-line
    )

    backend.run()


if __name__ == '__main__':
    main()
