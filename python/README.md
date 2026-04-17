# Laerdal QCPR Python Library

Python library for communicating with Laerdal QCPR mannequins over Bluetooth Low Energy.

## Installation

```bash
cd python
pip install -e .
```

## Quick Start

### Scan for devices

```bash
python -m laerdal_qcpr.examples.scan
```

### Simple compression logger

```bash
python -m laerdal_qcpr.examples.simple <device_address>
```

### Live dashboard

```bash
python -m laerdal_qcpr.examples.live_monitor <device_address> --duration 60
```

## Library Usage

### Async iterator (recommended)

```python
import asyncio
from laerdal_qcpr import QCPRClient

async def main():
    async with QCPRClient("XX:XX:XX:XX:XX:XX") as qcpr:
        await qcpr.start_streaming()

        async for compression in qcpr.compressions():
            print(f"#{qcpr.compression_count} "
                  f"Depth: {compression.peak_depth_mm} mm "
                  f"({compression.depth_quality.value}) "
                  f"Rate: {qcpr.current_rate:.0f}/min")

asyncio.run(main())
```

### Callback-based

```python
import asyncio
from laerdal_qcpr import QCPRClient

async def main():
    async with QCPRClient("XX:XX:XX:XX:XX:XX") as qcpr:
        # Real-time depth samples (~60 Hz)
        qcpr.on_depth = lambda s: print(f"Depth: {s.depth_mm} mm")

        # Per-compression summary
        qcpr.on_compression = lambda c: print(f"Peak: {c.peak_depth_mm} mm")

        await qcpr.start_streaming()
        await asyncio.sleep(30)
        await qcpr.stop_streaming()

        # Session summary
        stats = qcpr.get_session_stats()
        print(f"Compressions: {stats.total_compressions}")
        print(f"Avg depth: {stats.avg_depth_mm:.1f} mm")
        print(f"Rate: {stats.avg_rate_per_min:.0f}/min")
        print(f"Correct depth: {stats.correct_depth_pct:.0f}%")

asyncio.run(main())
```

### Device discovery

```python
from laerdal_qcpr.client import discover_qcpr_devices

devices = await discover_qcpr_devices(timeout=5.0)
for d in devices:
    print(f"{d.address} - {d.name}")
```

## API Reference

### `QCPRClient`

| Property | Type | Description |
|----------|------|-------------|
| `device_name` | `str` | Device name (e.g., "Little Anne QCPR") |
| `firmware` | `str` | Firmware version |
| `serial_number` | `str` | Serial number |
| `battery_level` | `int` | Battery percentage |
| `is_connected` | `bool` | Connection status |
| `is_streaming` | `bool` | Whether data stream is active |
| `compression_count` | `int` | Number of compressions in session |
| `current_rate` | `float` | Current rate (per minute, rolling 10s window) |

| Method | Description |
|--------|-------------|
| `connect()` | Connect and authenticate |
| `disconnect()` | Stop streaming and disconnect |
| `start_streaming()` | Start CPR data stream |
| `stop_streaming()` | Stop CPR data stream |
| `compressions()` | Async iterator yielding `Compression` objects |
| `get_session_stats()` | Get `SessionStats` for current session |

### Data Models

- **`CompressionSample`** — Single depth reading (timestamp, depth_mm)
- **`Compression`** — Completed compression (wall_time, peak_depth_mm, duration_ms, depth_quality)
- **`CompressionEvent`** — Raw event from device (timestamp, peak_depth_raw, duration_raw, flags)
- **`SessionStats`** — Session summary (total_compressions, avg_depth_mm, avg_rate_per_min, correct_depth_pct, depth_quality, rate_quality)
- **`DepthQuality`** — Enum: GOOD, TOO_SHALLOW, TOO_DEEP, NONE
- **`RateQuality`** — Enum: GOOD, TOO_SLOW, TOO_FAST, UNKNOWN

## Protocol Documentation

See the [project README](../README.md) for the full BLE protocol specification.
