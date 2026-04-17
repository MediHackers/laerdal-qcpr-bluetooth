# Laerdal QCPR Bluetooth Low Energy Protocol

Unofficial documentation of the BLE communication protocol used by Laerdal Little Anne QCPR (and potentially other Laerdal QCPR mannequins). This documentation was reverse-engineered from BLE packet captures of the official Laerdal QCPR app and verified with a working Python implementation.

> **Disclaimer:** This is an independent reverse-engineering effort. Laerdal Medical is not affiliated with this project. Use at your own risk. All trademarks belong to their respective owners.

## Table of Contents

- [Overview](#overview)
- [Device Discovery](#device-discovery)
- [GATT Service Structure](#gatt-service-structure)
- [Connection & Authentication](#connection--authentication)
- [Starting the CPR Data Stream](#starting-the-cpr-data-stream)
- [Data Characteristics](#data-characteristics)
  - [Real-time Compression Data (0x0027)](#real-time-compression-data-0x0027)
  - [Compression Event Summary (0x0028)](#compression-event-summary-0x0028)
  - [Periodic Statistics (0x012A)](#periodic-statistics-0x012a)
  - [Compression Count (0x0030)](#compression-count-0x0030)
  - [Session Counter (0x01A1)](#session-counter-0x01a1)
- [Stopping the Stream](#stopping-the-stream)
- [Full Connection Sequence](#full-connection-sequence)
- [Implementation Notes](#implementation-notes)
- [Reference Implementation](#reference-implementation)
- [Device Information](#device-information)

## Overview

The Laerdal QCPR sensor module communicates via Bluetooth Low Energy (BLE). It streams real-time chest compression data including depth (in mm), timing, and per-compression event summaries. The data can be used to build CPR training feedback applications.

**Key facts:**
- No pairing or bonding required
- Uses custom Laerdal BLE service UUIDs (base: `d746-4092-84e7-dad34863fe4a`)
- Requires a 20-byte authentication token written to the command characteristic before streaming
- Real-time data is streamed at approximately 60 Hz (~16 ms intervals)
- Compression events are emitted once per completed compression

## Device Discovery

The QCPR module advertises as a standard BLE peripheral. It can be discovered by scanning for devices with names containing Laerdal-related keywords.

**Known advertised names:**
- `Little Anne QCPR`
- `Laerdal QCPR`
- Names containing `QCPR`, `Laerdal`, or `Little Anne`

**Identification by service UUID:**

All custom characteristics share the UUID base `d746-4092-84e7-dad34863fe4a`. You can identify a QCPR device by checking if any advertised service UUIDs contain this base string.

## GATT Service Structure

The device exposes 13 services and 48 characteristics. Below are the services and characteristics relevant to CPR data streaming. All custom UUIDs follow the pattern `XXXXXXXX-d746-4092-84e7-dad34863fe4a`.

### Standard BLE Services

| Service | UUID | Characteristics |
|---------|------|-----------------|
| Generic Access | `0x1800` | Device Name (`0x2A00`), Appearance (`0x2A01`) |
| Device Information | `0x180A` | Manufacturer (`0x2A29`), Model (`0x2A24`), Serial (`0x2A25`), FW Rev (`0x2A26`), HW Rev (`0x2A27`), SW Rev (`0x2A28`) |
| Battery Service | `0x180F` | Battery Level (`0x2A19`, notify) |

### QCPR Data Service

| Short UUID | Full UUID | Properties | Description |
|------------|-----------|------------|-------------|
| `0x0027` | `00000027-d746-4092-84e7-dad34863fe4a` | Notify, Read | **Real-time compression depth** |
| `0x0028` | `00000028-d746-4092-84e7-dad34863fe4a` | Notify, Read | **Per-compression event summary** |
| `0x0030` | `00000030-d746-4092-84e7-dad34863fe4a` | Notify, Read | **Compression count** |
| `0x012A` | `0000012a-d746-4092-84e7-dad34863fe4a` | Notify, Read | **Periodic statistics (~1/s)** |
| `0x01A1` | `000001a1-d746-4092-84e7-dad34863fe4a` | Notify, Read | **Session counter** |

### QCPR Control Service

| Short UUID | Full UUID | Properties | Description |
|------------|-----------|------------|-------------|
| `0x0127` | `00000127-d746-4092-84e7-dad34863fe4a` | Indicate, Write, Read | **Config / stream control** |
| `0x01B1` | `000001b1-d746-4092-84e7-dad34863fe4a` | Write | **Command input (auth token)** |
| `0x01B2` | `000001b2-d746-4092-84e7-dad34863fe4a` | Notify, Read | **Command ACK / status** |
| `0x01E2` | `000001e2-d746-4092-84e7-dad34863fe4a` | Write | **Mode switch** (⚠ invalidates GATT table) |

### Other Characteristics (Configuration)

| Short UUID | Full UUID | Properties | Known Values |
|------------|-----------|------------|--------------|
| `0x0131` | `00000131-d746-4092-84e7-dad34863fe4a` | Notify, Read | Sensor data (secondary) |
| `0x0151` | `00000151-d746-4092-84e7-dad34863fe4a` | Notify, Read | Sensor config |
| `0x0153` | `00000153-d746-4092-84e7-dad34863fe4a` | Notify, Read | Sensor config |
| `0x0154` | `00000154-d746-4092-84e7-dad34863fe4a` | Notify, Read | Sensor config |
| `0x0200` | `00000200-d746-4092-84e7-dad34863fe4a` | Notify, Read | Unknown |
| `0x0201` | `00000201-d746-4092-84e7-dad34863fe4a` | Notify, Read | Unknown |
| `0x0251` | `00000251-d746-4092-84e7-dad34863fe4a` | Indicate, Read | Unknown |

### DFU Service

| Short UUID | Full UUID | Properties |
|------------|-----------|------------|
| `0x1531` | `00001531-1212-efde-1523-785feabcd123` | Notify | Nordic DFU control point |

> ⚠ **Warning:** Writing to the Mode Switch characteristic (`0x01E2`) will invalidate the GATT table and disconnect the device. Avoid writing to this characteristic during normal operation.

## Connection & Authentication

### Step 1: Connect

Connect to the device using its BLE address (or macOS UUID). No pairing or bonding is required.

### Step 2: Write Authentication Token

Write the following 20-byte token to the **Command** characteristic (`0x01B1`):

```
5c 0e b9 be 03 d2 60 09 6d 3e 1f 0c 80 26 c8 10 73 cd 2e a2
```

**Write type:** Write with Response (Write Request, ATT opcode `0x12`)

The device responds with an ACK (`0xAA`) notification on the Status characteristic (`0x01B2`).

> **Note:** This token appears to be static (same across sessions and devices of the same type). It may be firmware-version-specific. Tested with firmware `1.4.2.165`.

### Step 3: Subscribe to Notifications

Enable notifications (CCCD = `0x0001`) on the following characteristics:
- `0x0027` — Real-time compression data
- `0x0028` — Compression event summaries
- `0x012A` — Periodic statistics
- `0x0030` — Compression count
- `0x01A1` — Session counter

Enable indications (CCCD = `0x0002`) on:
- `0x0127` — Config/stream control

> **Important:** The Config characteristic (`0x0127`) uses BLE **Indications** (not Notifications). You **must** subscribe to indications on this characteristic **before** writing the start command. Otherwise the device returns GATT error 253 ("CCCD Improperly Configured").

### Step 4: Start Streaming

Write the following 3 bytes to the **Config** characteristic (`0x0127`):

```
03 ff 00
```

**Write type:** Write with Response

After this write, the device immediately begins streaming real-time compression data on characteristic `0x0027`.

## Data Characteristics

### Real-time Compression Data (`0x0027`)

**Direction:** Device → Client (Notification)
**Frequency:** ~60 Hz (every ~16 ms) during active compression
**Payload:** 5 bytes

```
Offset  Size  Type     Description
------  ----  ----     -----------
0       2     uint16   Timestamp (little-endian, units: ~0.16 ms, wraps at 0xFFFF)
2       2     uint16   Reserved (always 0x0000)
4       1     uint8    Compression depth in millimeters
```

**Depth values:**
- `0x00` (0 mm) — No compression / chest at rest
- `0x01`–`0x31` (1–49 mm) — Shallow compression
- `0x32`–`0x3C` (50–60 mm) — **Correct depth** per BLS guidelines
- `0x3D`+ (61+ mm) — Too deep

**Example data stream during one compression:**

```
a01b000000   →  ts=7072, depth=0mm  (rest)
2025000001   →  ts=9504, depth=1mm  (compression start)
4025000005   →  ts=9536, depth=5mm
802500000b   →  ts=9600, depth=11mm
c025000011   →  ts=9664, depth=17mm
0026000019   →  ts=9728, depth=25mm
202600001f   →  ts=9760, depth=31mm
4026000024   →  ts=9792, depth=36mm
8026000029   →  ts=9856, depth=41mm
a02600002f   →  ts=9888, depth=47mm  (peak)
c02600002e   →  ts=9920, depth=46mm  (release)
0027000025   →  ts=9984, depth=37mm
4027000018   →  ts=10048, depth=24mm
8027000011   →  ts=10112, depth=17mm
b02700000b   →  ts=10160, depth=11mm
e027000009   →  ts=10208, depth=9mm
002800000b   →  ts=10240, depth=11mm  (next compression)
```

**Peak detection algorithm:**
1. Track when depth rises above a threshold (e.g., 5 mm) — compression start
2. Track the maximum depth value during the compression
3. When depth drops below the threshold — compression end, record peak

### Compression Event Summary (`0x0028`)

**Direction:** Device → Client (Notification)
**Frequency:** Once per completed compression
**Payload:** 12 bytes

```
Offset  Size  Type     Description
------  ----  ----     -----------
0       2     uint16   Timestamp (LE) — matches real-time data timestamps
2       2     uint16   Reserved / padding
4       2     uint16   Peak depth value (LE, encoded)
6       2     uint16   Duration / timing metric (LE)
8       2     uint16   Position / displacement metric (LE)
10      2     uint16   Flags / status (LE)
```

**Example:**
```
80280000b0012fe0026e0100
│      │    │    │    └─ 0x016E (flags)
│      │    │    └────── 0x02E0 (timing)
│      │    └─────────── 0x012F (peak ~303 → maps to mm)
│      └──────────────── 0x00B0 (reserved)
└─────────────────────── 0x0028,0x0080 (timestamp)
```

> **Note:** The exact encoding of the peak depth in event summaries differs from the real-time depth byte. The relationship may involve a scaling factor. Use real-time data for accurate mm readings.

### Periodic Statistics (`0x012A`)

**Direction:** Device → Client (Notification)
**Frequency:** ~1 Hz (once per second during active session)
**Payload:** 12 bytes

```
Offset  Size  Type     Description
------  ----  ----     -----------
0       4     uint32   Session timestamp / counter (LE)
4       4     uint32   Cumulative data counter (LE)
8       4     uint32   Additional statistics (LE)
```

**Example sequence (1-second intervals):**
```
901b0000 901b0000 00000000   → session start (counters zeroed)
901b0000 801f0000 f0030000   → 1s in
901b0000 60230000 d0070000   → 2s in
901b0000 50270000 c00b0000   → 3s in
```

### Compression Count (`0x0030`)

**Direction:** Device → Client (Notification)
**Frequency:** Updated periodically during compressions
**Payload:** 2 bytes

```
Offset  Size  Type     Description
------  ----  ----     -----------
0       2     uint16   Total compression count (LE) since session start
```

**Example:** `0x0300` = 3 compressions, `0x0400` = 4 compressions.

### Session Counter (`0x01A1`)

**Direction:** Device → Client (Notification)
**Frequency:** Periodic (every few seconds)
**Payload:** 4 bytes

```
Offset  Size  Type     Description
------  ----  ----     -----------
0       1     uint8    Message type / opcode (observed: 0x03)
1       1     uint8    Compression count or session indicator
2       2     uint16   Reserved (observed: 0x0000)
```

**Examples:**
- `03020000` — 2 compressions completed
- `03000000` — Counter reset / idle

## Stopping the Stream

Write the following 3 bytes to the **Config** characteristic (`0x0127`):

```
00 00 00
```

**Write type:** Write with Response

The device stops sending real-time data notifications.

## Full Connection Sequence

Here is the complete sequence for a working CPR monitoring session:

```
1. CONNECT to device (no pairing needed)

2. WRITE to CMD (0x01B1):
   value: 5c0eb9be03d260096d3e1f0c8026c81073cd2ea2
   type:  Write Request (with response)

3. SUBSCRIBE to indications on CONFIG (0x0127):
   write CCCD descriptor: 0x0200

4. SUBSCRIBE to notifications on DATA (0x0027):
   write CCCD descriptor: 0x0100

5. SUBSCRIBE to notifications on EVENT (0x0028):
   write CCCD descriptor: 0x0100

6. SUBSCRIBE to notifications on other chars as needed:
   0x012A, 0x0030, 0x01A1
   write CCCD descriptor: 0x0100

7. WRITE to CONFIG (0x0127):
   value: 03ff00
   type:  Write Request (with response)
   → Device starts streaming CPR data

8. RECEIVE notifications on 0x0027 (real-time depth at ~60 Hz)
   RECEIVE notifications on 0x0028 (per-compression events)
   RECEIVE notifications on 0x012A, 0x0030, 0x01A1 (statistics)

9. WRITE to CONFIG (0x0127):
   value: 000000
   type:  Write Request (with response)
   → Device stops streaming

10. DISCONNECT
```

### Timing (from packet capture)

| Step | Relative Time | Operation |
|------|--------------|-----------|
| Connect | 0.0 s | BLE connection established |
| Auth token | +0.3 s | Write to CMD |
| Subscribe | +4.0 s | Enable CCCD on all chars |
| Start stream | +8.0 s | Write `03ff00` to CONFIG |
| First data | +8.1 s | First notification on `0x0027` |
| First event | +10.0 s | First compression event on `0x0028` |

## Implementation Notes

### Authentication Token

The 20-byte token `5c0eb9be03d260096d3e1f0c8026c81073cd2ea2` was captured from the official Laerdal QCPR app. It appears static across sessions. If this token stops working on future firmware versions, capture a new one using a BLE sniffer (e.g., Apple's PacketLogger via sysdiagnose, or nRF Connect).

### MTU

The device uses the minimum BLE MTU of 23 bytes. All payloads fit within this MTU, so no MTU negotiation is required.

### CCCD Order Matters

The Config characteristic (`0x0127`) uses BLE **Indications** (not Notifications). You must:
1. Write `0x0200` to its CCCD descriptor to enable indications
2. Only then write `03ff00` to the characteristic value

If you write to the characteristic before enabling indications, the device returns GATT error 253 ("CCCD Improperly Configured").

### Mode Switch Characteristic — Do Not Write

The Mode Switch characteristic (`0x01E2`) will invalidate the entire GATT table upon write, causing disconnection and making the device temporarily undiscoverable. Avoid writing to this characteristic.

### Platform Notes

| Platform | BLE Stack | Notes |
|----------|-----------|-------|
| macOS | CoreBluetooth | Uses UUID instead of MAC address. Works with `bleak`. |
| Linux | BlueZ | Uses MAC address. Works with `bleak`. |
| iOS | CoreBluetooth | Works natively. Apple requires Bluetooth usage description in Info.plist. |
| Android | Android BLE API | Standard BLE stack. |
| Windows | WinRT | Works with `bleak`. |

### BLS Quality Guidelines

For CPR quality assessment based on international BLS guidelines:

| Metric | Target Range |
|--------|-------------|
| Compression depth | 50–60 mm |
| Compression rate | 100–120 per minute |
| Full chest recoil | Depth returns to 0 between compressions |

### Minimal Python Example

```python
import asyncio
from bleak import BleakClient

DEVICE_ADDRESS = "XX:XX:XX:XX:XX:XX"  # or macOS UUID

CMD_UUID    = "000001b1-d746-4092-84e7-dad34863fe4a"
CONFIG_UUID = "00000127-d746-4092-84e7-dad34863fe4a"
DATA_UUID   = "00000027-d746-4092-84e7-dad34863fe4a"

AUTH_TOKEN = bytes.fromhex("5c0eb9be03d260096d3e1f0c8026c81073cd2ea2")


def on_data(char, data: bytearray):
    if len(data) >= 5:
        depth_mm = data[4]
        print(f"Depth: {depth_mm} mm")


async def main():
    async with BleakClient(DEVICE_ADDRESS) as client:
        # 1. Authenticate
        await client.write_gatt_char(CMD_UUID, AUTH_TOKEN, response=True)

        # 2. Subscribe (CONFIG must be subscribed before writing to it)
        await client.start_notify(CONFIG_UUID, lambda c, d: None)
        await client.start_notify(DATA_UUID, on_data)

        # 3. Start streaming
        await client.write_gatt_char(CONFIG_UUID, b"\x03\xff\x00", response=True)

        # 4. Monitor for 30 seconds
        await asyncio.sleep(30)

        # 5. Stop streaming
        await client.write_gatt_char(CONFIG_UUID, b"\x00\x00\x00", response=True)


asyncio.run(main())
```

## Device Information

Tested with the following device:

| Field | Value |
|-------|-------|
| Device | Little Anne QCPR |
| Manufacturer | Laerdal Medical |
| Firmware | 1.4.2.165 |
| Hardware | (via `0x2A27`) |
| Serial Number | 4931-40094C |
| BLE Services | 13 |
| BLE Characteristics | 48 |
| MTU | 23 (minimum) |

## Protocol Discovery Method

This protocol was reverse-engineered using:

1. **BLE GATT enumeration** via `bleak` (Python) — mapped all 48 characteristics
2. **HCI packet capture** via Apple's Bluetooth logging profile (sysdiagnose) — captured the official Laerdal QCPR iOS app communicating with the device
3. **Packet analysis** with a custom `.pklg` parser — extracted the initialization sequence  
4. **Protocol replay** — verified the captured sequence produces working data streams

## Contributing

If you discover additional protocol details (e.g., ventilation data, different mannequin models, newer firmware behavior), please open an issue or pull request.

## License

MIT License — see [LICENSE](LICENSE) for details.
