"""Laerdal QCPR Bluetooth Low Energy library.

A Python library for communicating with Laerdal QCPR mannequins
(Little Anne QCPR and compatible models) over Bluetooth Low Energy.

Example usage::

    import asyncio
    from laerdal_qcpr import QCPRClient

    async def main():
        async with QCPRClient("XX:XX:XX:XX:XX:XX") as qcpr:
            await qcpr.start_streaming()

            async for event in qcpr.compressions():
                print(f"Depth: {event.peak_depth_mm} mm, "
                      f"Rate: {event.rate_per_min:.0f}/min")

    asyncio.run(main())
"""

from .client import QCPRClient
from .models import (
    CompressionSample,
    CompressionEvent,
    SessionStats,
    DepthQuality,
    RateQuality,
)
from .protocol import (
    QCPR_CMD_UUID,
    QCPR_CONFIG_UUID,
    QCPR_DATA_UUID,
    QCPR_EVENT_UUID,
    QCPR_STATS_UUID,
    QCPR_COUNT_UUID,
    QCPR_SESSION_UUID,
    QCPR_STATUS_UUID,
    AUTH_TOKEN,
)

__version__ = "0.1.0"

__all__ = [
    "QCPRClient",
    "CompressionSample",
    "CompressionEvent",
    "SessionStats",
    "DepthQuality",
    "RateQuality",
    "QCPR_CMD_UUID",
    "QCPR_CONFIG_UUID",
    "QCPR_DATA_UUID",
    "QCPR_EVENT_UUID",
    "QCPR_STATS_UUID",
    "QCPR_COUNT_UUID",
    "QCPR_SESSION_UUID",
    "QCPR_STATUS_UUID",
    "AUTH_TOKEN",
]
