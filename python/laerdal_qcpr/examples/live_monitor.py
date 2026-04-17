#!/usr/bin/env python3
"""Example: Live CPR monitoring dashboard.

Usage:
    python -m laerdal_qcpr.examples.live_monitor <device_address> [--duration 60]

    device_address: BLE address (Linux/Windows) or UUID (macOS)
"""

import argparse
import asyncio
import sys

from laerdal_qcpr import QCPRClient
from laerdal_qcpr.protocol import BLS_DEPTH_MIN_MM, BLS_DEPTH_MAX_MM


def render_bar(depth: int, width: int = 40) -> str:
    max_display = 70
    filled = min(int(depth / max_display * width), width)
    bar = "█" * filled + "░" * (width - filled)
    if depth == 0:
        return f"[{bar}]"
    elif depth < BLS_DEPTH_MIN_MM:
        return f"[{bar}] ⚠ SHALLOW"
    elif depth <= BLS_DEPTH_MAX_MM:
        return f"[{bar}] ✓ GOOD"
    else:
        return f"[{bar}] ⚠ TOO DEEP"


async def main(address: str, duration: float) -> None:
    current_depth = 0

    async with QCPRClient(address) as qcpr:
        print(f"Device: {qcpr.device_name}")
        print(f"Firmware: {qcpr.firmware}")
        print(f"Serial: {qcpr.serial_number}")
        print(f"Battery: {qcpr.battery_level}%")
        print()

        def on_depth(sample):
            nonlocal current_depth
            current_depth = sample.depth_mm

        qcpr.on_depth = on_depth
        await qcpr.start_streaming()

        start = asyncio.get_event_loop().time()
        try:
            while (asyncio.get_event_loop().time() - start) < duration:
                stats = qcpr.get_session_stats()
                rate = qcpr.current_rate

                print(f"\033[2J\033[H", end="")
                print(f"{'═'*60}")
                print(f"  QCPR LIVE MONITOR  │  {int(asyncio.get_event_loop().time() - start)}s")
                print(f"{'═'*60}")
                print()
                print(f"  Depth: {current_depth:3d} mm  {render_bar(current_depth)}")
                print()
                print(f"  Compressions: {stats.total_compressions:4d}")
                print(f"  Rate:         {rate:5.0f} /min  (target 100-120)")
                print(f"  Avg depth:    {stats.avg_depth_mm:5.1f} mm  (target 50-60)")
                print(f"  Min / Max:    {stats.min_depth_mm:3d} / {stats.max_depth_mm:3d} mm")

                if stats.compressions:
                    print(f"\n  Last compressions:")
                    for c in stats.compressions[-5:]:
                        q = "✓" if c.depth_quality.value == "good" else "⚠"
                        print(f"    {c.wall_time:6.1f}s │ {c.peak_depth_mm:3d} mm │ {c.duration_ms:3d}ms │ {q}")

                print(f"\n  Press Ctrl+C to stop.")
                await asyncio.sleep(0.3)

        except asyncio.CancelledError:
            pass

        await qcpr.stop_streaming()

    # Final summary
    stats = qcpr.get_session_stats()
    print(f"\033[2J\033[H", end="")
    print(f"\n{'═'*60}")
    print(f"  SESSION SUMMARY")
    print(f"{'═'*60}")
    print(f"  Duration:      {stats.duration_s:.0f}s")
    print(f"  Compressions:  {stats.total_compressions}")
    print(f"  Rate:          {stats.avg_rate_per_min:.0f}/min  ({stats.rate_quality.value})")
    print(f"  Avg depth:     {stats.avg_depth_mm:.1f} mm  ({stats.depth_quality.value})")
    print(f"  Correct depth: {stats.correct_depth_pct:.0f}%")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live QCPR monitor")
    parser.add_argument("address", help="BLE device address or UUID")
    parser.add_argument("-d", "--duration", type=float, default=60.0)
    args = parser.parse_args()

    try:
        asyncio.run(main(args.address, args.duration))
    except KeyboardInterrupt:
        print("\nStopped.")
