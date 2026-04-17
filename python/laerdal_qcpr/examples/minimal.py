"""Minimal example: connect, stream, print depth.

Usage:
    python minimal.py <device_address>
"""

import asyncio
import sys
from laerdal_qcpr import QCPRClient


async def main():
    async with QCPRClient(sys.argv[1]) as qcpr:
        print(f"Connected to {qcpr.device_name} (battery {qcpr.battery_level}%)")

        await qcpr.start_streaming()

        async for c in qcpr.compressions():
            q = "✓" if c.depth_quality.value == "good" else "⚠"
            print(f"  {c.peak_depth_mm:3d} mm  {c.duration_ms}ms  {q}")

asyncio.run(main())
