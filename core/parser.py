"""
SSI BUSD JSON Parser

Parses SSI WebSocket data format from HOSE BUSD stream.
"""

import json
from dataclasses import dataclass
from typing import Optional


@dataclass
class Bubble:
    """
    Represents a single matched trade (bubble) from SSI data.

    Attributes:
        stock: Stock symbol (e.g., 'HPG', 'VNM')
        volume: Matching volume
        price: Trade price
        serverTime: Server timestamp in microseconds (for detection)
        timestamp: HOSE server timestamp in milliseconds (for output)
        side: Trade side - 'bu' (buy up) or 'sd' (sell down)
        is_vwap: Flag indicating if this bubble is part of a VWAP pattern
    """
    stock: str
    volume: int
    price: float
    serverTime: int  # microseconds
    timestamp: int   # milliseconds
    side: str        # 'bu' or 'sd'
    is_vwap: bool = False


def parse_ssi_busd_line(line: str) -> Optional[Bubble]:
    """
    Parse a single line from SSI HOSE BUSD JSON stream.

    Expected format (post-KRX, includes serverTime payload at index 12):
    {
      "timestamp": 1697681700817,
      "data": {
        "response": {
          "payloadData": "MAIN|L#BIC|24150|1000|1000|09:14:59|23800|bu|350|1.47|U||1697681699000"
        }
      }
    }

    PayloadData format (pipe-delimited):
    [0]  type         = "MAIN"
    [1]  stock        = "L#BIC" (strip "L#" prefix)
    [2]  last         = 24150 (price)
    [3]  matchingVol  = 1000 (volume)
    [4]  totalVol     = 1000
    [5]  time         = "09:14:59"
    [6]  refPrice     = 23800
    [7]  matchedBy    = "bu" or "sd"
    [8]  change       = 350
    [9]  changePct    = 1.47
    [10] urd          = "U"
    [11] typeAgain    = (optional)
    [12] serverTime   = 1697681699000 (milliseconds)

    Args:
        line: JSON string from SSI WebSocket stream

    Returns:
        Bubble object if parsing successful, None otherwise
    """
    try:
        # Parse JSON
        msg = json.loads(line.strip())

        # Extract payloadData
        payload_data = msg.get('data', {}).get('response', {}).get('payloadData')
        if not payload_data:
            return None

        # Parse pipe-delimited payload
        fields = payload_data.split('|')

        # Validate minimum fields (need serverTime at index 12)
        if len(fields) < 13:
            return None

        # Check if this is a MAIN lot trade
        if fields[0] != 'MAIN':
            return None

        # Extract stock symbol (strip "L#" prefix if present)
        stock = fields[1]
        if stock.startswith('L#'):
            stock = stock[2:]

        # Extract price and volume
        try:
            price = float(fields[2])
            volume = int(fields[3])
        except (ValueError, IndexError):
            return None

        # Extract matchedBy (bu/sd)
        matched_by = fields[7].lower()
        if matched_by not in ('bu', 'sd'):
            return None

        # Extract serverTime (convert from milliseconds to microseconds for detection)
        try:
            server_time_ms = int(fields[12])
        except (ValueError, IndexError):
            return None

        # serverTime is mandatory in post-KRX data
        server_time_us = server_time_ms * 1000  # milliseconds to microseconds
        timestamp_ms = server_time_ms

        # Validate volume and price
        if volume <= 0 or price <= 0:
            return None

        # Create Bubble object
        return Bubble(
            stock=stock,
            volume=volume,
            price=price,
            serverTime=server_time_us,
            timestamp=timestamp_ms,
            side=matched_by,
            is_vwap=False
        )

    except (json.JSONDecodeError, KeyError, TypeError):
        return None
