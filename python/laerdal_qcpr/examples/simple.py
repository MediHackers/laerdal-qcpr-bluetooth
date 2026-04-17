#!/usr/bin/env python3
"""Example: Simple compression logger.

Connects to a QCPR device and prints each compression as it happens.
Minimal example showing async iterator usage.

Usage:
    python -m laerdal_qcpr.examples.simple <device_address>
"""

import asyncio
import sys

from laerdal_qcpr import QCPRClient


async def main(address: str) -> None:
    async with QCPRClient(address) as qcpr:
        print(f"Connected to {qcpr.device_name} (FW {qcpr.firmware})")
        print(f"Battery: {qcpr.battery_level}%")
        print("Starting stream... Press the mannequin chest!")
        print()

        await qcpr.start_streaming()

        async for compression in qcpr.compressions():
            rate = qcpr.current_rate
            q = "✓" if compression.depth_quality.value == "good" else "⚠"
            print(
                f"  #{qcpr.compression_count:3d}  "
                f"{compression.peak_depth_mm:3d} mm  "
                f"{compression.duration_ms:3d} ms  "
                f"{rate:5.1f}/min  {q}"
            )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python -m laerdal_qcpr.examples.simple <address>")
        sys.exit(1)

    try:
        asyncio.run(main(sys.argv[1]))
    except KeyboardInterrupt:
        print("\nStopped.")
