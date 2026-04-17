#!/usr/bin/env python3
"""Example: Scan for QCPR devices.

Usage:
    python -m laerdal_qcpr.examples.scan [--timeout 5]
"""

import argparse
import asyncio

from laerdal_qcpr.client import discover_qcpr_devices


async def main(timeout: float) -> None:
    print(f"Scanning for QCPR devices ({timeout}s) ...")
    devices = await discover_qcpr_devices(timeout=timeout)

    if not devices:
        print("No QCPR devices found.")
        return

    print(f"\nFound {len(devices)} device(s):\n")
    for d in devices:
        print(f"  {d.address}  {d.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scan for QCPR devices")
    parser.add_argument("-t", "--timeout", type=float, default=5.0)
    args = parser.parse_args()
    asyncio.run(main(args.timeout))
