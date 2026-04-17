"""BLE client for Laerdal QCPR devices."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator, Callable, Optional

from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice

from .models import (
    Compression,
    CompressionEvent,
    CompressionSample,
    SessionStats,
)
from .protocol import (
    AUTH_TOKEN,
    CMD_START_STREAM,
    CMD_STOP_STREAM,
    LAERDAL_UUID_BASE,
    QCPR_CMD_UUID,
    QCPR_CONFIG_UUID,
    QCPR_COUNT_UUID,
    QCPR_DATA_UUID,
    QCPR_EVENT_UUID,
    QCPR_SESSION_UUID,
    QCPR_STATS_UUID,
    QCPR_STATUS_UUID,
)

logger = logging.getLogger(__name__)

# Minimum depth (mm) to start counting as a compression
_DEPTH_THRESHOLD = 5


async def discover_qcpr_devices(timeout: float = 5.0) -> list[BLEDevice]:
    """Scan for Laerdal QCPR devices.

    Returns a list of BLE devices whose names contain QCPR-related keywords.
    """
    keywords = ("qcpr", "laerdal", "little anne", "resusci")
    devices = await BleakScanner.discover(timeout=timeout)
    return [
        d
        for d in devices
        if d.name and any(kw in d.name.lower() for kw in keywords)
    ]


class QCPRClient:
    """High-level async client for Laerdal QCPR mannequins.

    Usage::

        async with QCPRClient("XX:XX:XX:XX:XX:XX") as qcpr:
            await qcpr.start_streaming()

            # Option A: callback-based
            qcpr.on_depth = lambda sample: print(sample.depth_mm)

            # Option B: iterate compressions
            async for compression in qcpr.compressions():
                print(compression.peak_depth_mm)

    The client handles authentication, CCCD subscription ordering,
    and stream start/stop automatically.
    """

    def __init__(
        self,
        address: str,
        auth_token: bytes = AUTH_TOKEN,
        depth_threshold: int = _DEPTH_THRESHOLD,
    ) -> None:
        self._address = address
        self._auth_token = auth_token
        self._depth_threshold = depth_threshold
        self._client: Optional[BleakClient] = None
        self._streaming = False
        self._session_start: float = 0.0

        # Callbacks (user-assignable)
        self.on_depth: Optional[Callable[[CompressionSample], None]] = None
        self.on_compression: Optional[Callable[[Compression], None]] = None
        self.on_event: Optional[Callable[[CompressionEvent], None]] = None

        # Internal state for peak detection
        self._in_compression = False
        self._current_peak = 0
        self._compression_start = 0.0
        self._compressions: list[Compression] = []
        self._compression_queue: Optional[asyncio.Queue[Compression]] = None

        # Device info cache
        self._device_name: Optional[str] = None
        self._firmware: Optional[str] = None
        self._serial: Optional[str] = None
        self._battery: Optional[int] = None

    # ------------------------------------------------------------------
    #  Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> QCPRClient:
        await self.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.disconnect()

    # ------------------------------------------------------------------
    #  Connection
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Connect to the QCPR device and authenticate."""
        if self._client and self._client.is_connected:
            return

        logger.info("Connecting to %s ...", self._address)
        self._client = BleakClient(self._address)
        await self._client.connect()
        logger.info("Connected. MTU: %d", self._client.mtu_size)

        # Read device info
        await self._read_device_info()

        # Authenticate
        logger.info("Authenticating ...")
        await self._client.write_gatt_char(
            QCPR_CMD_UUID, self._auth_token, response=True
        )
        logger.info("Authenticated.")

    async def disconnect(self) -> None:
        """Stop streaming and disconnect."""
        if self._streaming:
            await self.stop_streaming()
        if self._client and self._client.is_connected:
            await self._client.disconnect()
            logger.info("Disconnected.")
        self._client = None

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    @property
    def is_streaming(self) -> bool:
        return self._streaming

    # ------------------------------------------------------------------
    #  Device info
    # ------------------------------------------------------------------

    @property
    def device_name(self) -> Optional[str]:
        return self._device_name

    @property
    def firmware(self) -> Optional[str]:
        return self._firmware

    @property
    def serial_number(self) -> Optional[str]:
        return self._serial

    @property
    def battery_level(self) -> Optional[int]:
        return self._battery

    async def _read_device_info(self) -> None:
        assert self._client
        for uuid, attr in [
            ("00002a00-0000-1000-8000-00805f9b34fb", "_device_name"),
            ("00002a26-0000-1000-8000-00805f9b34fb", "_firmware"),
            ("00002a25-0000-1000-8000-00805f9b34fb", "_serial"),
        ]:
            try:
                raw = await self._client.read_gatt_char(uuid)
                setattr(self, attr, raw.decode("utf-8", errors="replace"))
            except Exception:
                pass
        try:
            raw = await self._client.read_gatt_char(
                "00002a19-0000-1000-8000-00805f9b34fb"
            )
            self._battery = raw[0] if raw else None
        except Exception:
            pass

    # ------------------------------------------------------------------
    #  Streaming
    # ------------------------------------------------------------------

    async def start_streaming(self) -> None:
        """Subscribe to characteristics and start the CPR data stream.

        Call this after connecting. The device will begin sending real-time
        compression data at ~60 Hz.
        """
        if self._streaming:
            return
        assert self._client and self._client.is_connected

        # Subscribe to CONFIG (indicate) FIRST — required before writing
        await self._client.start_notify(QCPR_CONFIG_UUID, self._on_config)

        # Subscribe to data characteristics
        await self._client.start_notify(QCPR_DATA_UUID, self._on_data)

        for uuid, handler in [
            (QCPR_EVENT_UUID, self._on_event),
            (QCPR_STATS_UUID, self._on_stats),
            (QCPR_COUNT_UUID, self._on_count),
            (QCPR_SESSION_UUID, self._on_session),
            (QCPR_STATUS_UUID, self._on_status),
        ]:
            try:
                await self._client.start_notify(uuid, handler)
            except Exception:
                logger.debug("Could not subscribe to %s", uuid)

        # Start streaming
        await self._client.write_gatt_char(
            QCPR_CONFIG_UUID, CMD_START_STREAM, response=True
        )

        self._session_start = asyncio.get_event_loop().time()
        self._streaming = True
        self._compressions.clear()
        self._in_compression = False
        self._current_peak = 0

        logger.info("CPR data stream started.")

    async def stop_streaming(self) -> None:
        """Stop the CPR data stream."""
        if not self._streaming:
            return
        assert self._client

        try:
            await self._client.write_gatt_char(
                QCPR_CONFIG_UUID, CMD_STOP_STREAM, response=True
            )
        except Exception:
            logger.debug("Error stopping stream", exc_info=True)

        self._streaming = False
        logger.info("CPR data stream stopped.")

        # Signal the compression queue that we're done
        if self._compression_queue:
            await self._compression_queue.put(None)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    #  Async iteration over compressions
    # ------------------------------------------------------------------

    async def compressions(self) -> AsyncIterator[Compression]:
        """Async iterator that yields each completed compression.

        Usage::

            async for c in qcpr.compressions():
                print(f"{c.peak_depth_mm} mm")

        Iteration ends when streaming is stopped.
        """
        self._compression_queue = asyncio.Queue()
        try:
            while True:
                item = await self._compression_queue.get()
                if item is None:
                    break
                yield item
        finally:
            self._compression_queue = None

    # ------------------------------------------------------------------
    #  Session summary
    # ------------------------------------------------------------------

    def get_session_stats(self) -> SessionStats:
        """Get cumulative statistics for the current/last session."""
        now = asyncio.get_event_loop().time()
        duration = now - self._session_start if self._session_start else 0
        return SessionStats.from_compressions(self._compressions, duration)

    @property
    def compression_count(self) -> int:
        return len(self._compressions)

    @property
    def current_rate(self) -> float:
        """Current compression rate (per minute) based on last 10 seconds."""
        if len(self._compressions) < 2:
            return 0.0
        now = asyncio.get_event_loop().time()
        t0 = now - self._session_start
        recent = [c for c in self._compressions if t0 - c.wall_time < 10.0]
        if len(recent) < 2:
            return 0.0
        span = recent[-1].wall_time - recent[0].wall_time
        if span <= 0:
            return 0.0
        return (len(recent) - 1) / span * 60.0

    # ------------------------------------------------------------------
    #  Internal notification handlers
    # ------------------------------------------------------------------

    def _on_data(self, _char: BleakGATTCharacteristic, data: bytearray) -> None:
        sample = CompressionSample.from_bytes(data)
        if sample is None:
            return

        # User callback
        if self.on_depth:
            self.on_depth(sample)

        # Peak detection
        depth = sample.depth_mm
        now = asyncio.get_event_loop().time()
        wall = now - self._session_start

        if not self._in_compression and depth >= self._depth_threshold:
            self._in_compression = True
            self._current_peak = depth
            self._compression_start = wall
        elif self._in_compression:
            if depth > self._current_peak:
                self._current_peak = depth
            if depth < self._depth_threshold:
                self._in_compression = False
                compression = Compression(
                    wall_time=self._compression_start,
                    peak_depth_mm=self._current_peak,
                    duration_ms=int((wall - self._compression_start) * 1000),
                )
                self._compressions.append(compression)
                self._current_peak = 0

                if self.on_compression:
                    self.on_compression(compression)
                if self._compression_queue:
                    self._compression_queue.put_nowait(compression)

    def _on_event(self, _char: BleakGATTCharacteristic, data: bytearray) -> None:
        event = CompressionEvent.from_bytes(data)
        if event and self.on_event:
            self.on_event(event)

    def _on_config(self, _char: BleakGATTCharacteristic, _data: bytearray) -> None:
        pass  # Required subscription, no action needed

    def _on_stats(self, _char: BleakGATTCharacteristic, _data: bytearray) -> None:
        logger.debug("Stats: %s", _data.hex())

    def _on_count(self, _char: BleakGATTCharacteristic, data: bytearray) -> None:
        if len(data) >= 2:
            count = int.from_bytes(data[0:2], "little")
            logger.debug("Device compression count: %d", count)

    def _on_session(self, _char: BleakGATTCharacteristic, _data: bytearray) -> None:
        logger.debug("Session: %s", _data.hex())

    def _on_status(self, _char: BleakGATTCharacteristic, data: bytearray) -> None:
        logger.debug("Status/ACK: %s", data.hex())
