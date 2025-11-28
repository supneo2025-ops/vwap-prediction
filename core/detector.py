"""
Fast VWAP Detector

Real-time VWAP pattern detection using sliding window approach.
Adapted from gen_vwap_live_v3.py for streaming detection.
"""

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, Tuple, List
from .parser import Bubble


@dataclass
class VWAPState:
    """
    Current VWAP state at a given timestamp.

    Attributes:
        timestamp: Current timestamp in milliseconds
        bu_vwap: Cumulative BU VWAP in billions
        sd_vwap: Cumulative SD VWAP in billions
        busd_vwap: Net VWAP (BU - SD) in billions
    """
    timestamp: int
    bu_vwap: float
    sd_vwap: float
    busd_vwap: float


class FastVWAPDetector:
    """
    Real-time VWAP pattern detector.

    Detects VWAP patterns by tracking (stock, volume) repetitions
    within a sliding time window.

    Algorithm:
    1. Track bubbles per (stock, volume) key in sliding window
    2. If pattern seen >= min_occurrences times, flag as VWAP
    3. Accumulate VWAP value for flagged bubbles
    4. Clean up old bubbles outside window periodically
    """

    def __init__(
        self,
        window_seconds: int = 300,
        min_occurrences: int = 5,
        volume_threshold: int = 200,
        cleanup_interval: int = 100
    ):
        """
        Initialize VWAP detector.

        Args:
            window_seconds: Lookback window for pattern detection (default 300s = 5 min)
            min_occurrences: Minimum repetitions to flag as VWAP pattern (default 5)
            volume_threshold: Ignore bubbles with volume below this (default 200)
            cleanup_interval: Clean old bubbles every N new bubbles (default 100)
        """
        self.window_ms = window_seconds * 1000  # Convert to milliseconds
        self.min_occurrences = min_occurrences
        self.volume_threshold = volume_threshold
        self.cleanup_interval = cleanup_interval

        # Pattern tracking: key = (stock, volume)
        # value = deque of bubbles with that (stock, volume)
        self.bu_patterns: Dict[Tuple[str, int], deque] = defaultdict(deque)
        self.sd_patterns: Dict[Tuple[str, int], deque] = defaultdict(deque)

        # VWAP cumulative sums (in billions)
        self.bu_vwap_cumsum: float = 0.0
        self.sd_vwap_cumsum: float = 0.0

        # Counter for cleanup
        self._bubble_count: int = 0

    def add_bubble(self, bubble: Bubble) -> VWAPState:
        """
        Process a new bubble and update VWAP state.

        This is the hot path - optimized for minimal operations.

        Args:
            bubble: Bubble object to process

        Returns:
            Current VWAP state after processing this bubble
        """
        # Filter low volume
        if bubble.volume <= self.volume_threshold:
            return self._get_current_state(bubble.timestamp)

        # Pattern key
        pattern_key = (bubble.stock, bubble.volume)

        # Select pattern dict based on side
        if bubble.side == 'bu':
            patterns = self.bu_patterns
        elif bubble.side == 'sd':
            patterns = self.sd_patterns
        else:
            return self._get_current_state(bubble.timestamp)

        # Get or create pattern deque
        pattern_deque = patterns[pattern_key]

        # Check if pattern ALREADY exists BEFORE adding current bubble
        # Pattern exists if we have >= min_occurrences bubbles in window
        is_vwap_pattern = len(pattern_deque) >= self.min_occurrences

        # If this is a VWAP pattern, accumulate the value
        if is_vwap_pattern:
            bubble.is_vwap = True
            vwap_value = (bubble.volume * bubble.price) / 1e9  # Convert to billions

            if bubble.side == 'bu':
                self.bu_vwap_cumsum += vwap_value
            else:  # sd
                self.sd_vwap_cumsum += vwap_value

        # Add bubble to pattern deque AFTER checking and accumulating
        pattern_deque.append(bubble)

        # Periodic cleanup
        self._bubble_count += 1
        if self._bubble_count % self.cleanup_interval == 0:
            self._cleanup_old_bubbles(bubble.timestamp)

        # Return current state
        return self._get_current_state(bubble.timestamp)

    def _cleanup_old_bubbles(self, current_time_ms: int):
        """
        Remove bubbles outside the lookback window.

        Args:
            current_time_ms: Current timestamp in milliseconds
        """
        cutoff_time = current_time_ms - self.window_ms

        # Clean BU patterns
        for pattern_key, pattern_deque in list(self.bu_patterns.items()):
            while pattern_deque and pattern_deque[0].timestamp < cutoff_time:
                pattern_deque.popleft()

            # Remove empty patterns
            if not pattern_deque:
                del self.bu_patterns[pattern_key]

        # Clean SD patterns
        for pattern_key, pattern_deque in list(self.sd_patterns.items()):
            while pattern_deque and pattern_deque[0].timestamp < cutoff_time:
                pattern_deque.popleft()

            # Remove empty patterns
            if not pattern_deque:
                del self.sd_patterns[pattern_key]

    def _get_current_state(self, timestamp: int) -> VWAPState:
        """
        Get current VWAP state.

        Args:
            timestamp: Current timestamp in milliseconds

        Returns:
            VWAPState object with current cumulative values
        """
        return VWAPState(
            timestamp=timestamp,
            bu_vwap=self.bu_vwap_cumsum,
            sd_vwap=self.sd_vwap_cumsum,
            busd_vwap=self.bu_vwap_cumsum - self.sd_vwap_cumsum
        )

    def get_timeseries(self) -> List[VWAPState]:
        """
        Get VWAP timeseries data.

        Note: This simple version doesn't maintain a full timeseries.
        For production, you'd maintain a list of (timestamp, state) tuples.

        Returns:
            List of VWAPState objects (currently just returns current state)
        """
        # For V1, we just track cumulative state
        # Frontend will build timeseries from Plasma updates
        return []
