#!/usr/bin/env python3
"""
Backend Controller
Manages the VWAP backend process, allowing dynamic restart with new settings
"""

import subprocess
import signal
import os
import sys
import time
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BackendController:
    """Controls the VWAP backend process"""

    def __init__(self):
        self.process = None
        self.data_dir = Path("/d/data/ssi/ws")
        self.backend_script = Path(__file__).parent / "vwap_prediction_backend.py"
        self.python_bin = "/Users/m2/anaconda3/envs/quantum/bin/python"

    def get_available_days(self):
        """Get list of available trading days"""
        files = list(self.data_dir.glob("*_ssi_hose_busd.received.txt"))
        days = []
        for f in files:
            # Extract date from filename: YYYY_MM_DD_ssi_hose_busd.received.txt
            parts = f.stem.split('_')
            if len(parts) >= 3:
                date_str = f"{parts[0]}-{parts[1]}-{parts[2]}"
                days.append(date_str)
        return sorted(days, reverse=True)  # Most recent first

    def start_backend(self, day: str, speed: float):
        """
        Start backend with specified day and speed

        Args:
            day: Date string in format YYYY-MM-DD
            speed: Speed multiplier (e.g., 5.0 for 5x)
        """
        # Stop existing process if running
        self.stop_backend()

        # Convert day format: YYYY-MM-DD -> YYYY_MM_DD
        day_file = day.replace('-', '_')
        data_file = self.data_dir / f"{day_file}_ssi_hose_busd.received.txt"

        if not data_file.exists():
            logger.error(f"Data file not found: {data_file}")
            return False

        logger.info(f"Starting backend: day={day}, speed={speed}x, file={data_file}")

        # Create modified backend script with settings
        # We'll modify the main() function to use these settings
        cmd = f"cat {data_file} | {self.python_bin} {self.backend_script} --speed {speed}"

        # Start process
        self.process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid  # Create new process group
        )

        logger.info(f"Backend started with PID: {self.process.pid}")
        return True

    def stop_backend(self):
        """Stop the backend process"""
        if self.process:
            try:
                # Kill the entire process group
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                self.process.wait(timeout=5)
                logger.info("Backend stopped")
            except ProcessLookupError:
                logger.warning("Process already terminated")
            except subprocess.TimeoutExpired:
                # Force kill if graceful shutdown fails
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                logger.warning("Backend force killed")
            finally:
                self.process = None

    def restart_backend(self, day: str, speed: float):
        """Restart backend with new settings"""
        logger.info(f"Restarting backend: day={day}, speed={speed}x")
        return self.start_backend(day, speed)

    def is_running(self):
        """Check if backend is running"""
        if self.process is None:
            return False
        return self.process.poll() is None


if __name__ == "__main__":
    # Simple CLI for testing
    import argparse

    parser = argparse.ArgumentParser(description="Control VWAP backend")
    parser.add_argument("action", choices=["start", "stop", "restart", "list"])
    parser.add_argument("--day", help="Trading day (YYYY-MM-DD)")
    parser.add_argument("--speed", type=float, default=5.0, help="Speed multiplier")

    args = parser.parse_args()

    controller = BackendController()

    if args.action == "list":
        days = controller.get_available_days()
        print("Available days:")
        for day in days:
            print(f"  {day}")
    elif args.action == "start":
        if not args.day:
            print("Error: --day required for start")
            sys.exit(1)
        controller.start_backend(args.day, args.speed)
        # Keep running
        try:
            while controller.is_running():
                time.sleep(1)
        except KeyboardInterrupt:
            controller.stop_backend()
    elif args.action == "stop":
        controller.stop_backend()
    elif args.action == "restart":
        if not args.day:
            print("Error: --day required for restart")
            sys.exit(1)
        controller.restart_backend(args.day, args.speed)
