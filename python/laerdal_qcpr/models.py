"""Data models for QCPR measurements."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional


class DepthQuality(enum.Enum):
    """Assessment of compression depth against BLS guidelines (50-60 mm)."""

    GOOD = "good"
    TOO_SHALLOW = "too_shallow"
    TOO_DEEP = "too_deep"
    NONE = "none"


class RateQuality(enum.Enum):
    """Assessment of compression rate against BLS guidelines (100-120/min)."""

    GOOD = "good"
    TOO_SLOW = "too_slow"
    TOO_FAST = "too_fast"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CompressionSample:
    """A single real-time depth sample from characteristic 0x0027.

    Received at ~60 Hz during active compressions.

    Attributes:
        timestamp: Device timestamp (little-endian uint16, wraps at 0xFFFF).
        depth_mm: Current chest compression depth in millimeters.
        raw: Original 5-byte payload.
    """

    timestamp: int
    depth_mm: int
    raw: bytes

    @classmethod
    def from_bytes(cls, data: bytes) -> Optional[CompressionSample]:
        """Parse a 5-byte notification payload.

        Format::

            Offset  Size  Type     Description
            0       2     uint16   Timestamp (LE)
            2       2     uint16   Reserved (0x0000)
            4       1     uint8    Depth in mm
        """
        if len(data) < 5:
            return None
        ts = int.from_bytes(data[0:2], "little")
        depth = data[4]
        return cls(timestamp=ts, depth_mm=depth, raw=bytes(data))

    @property
    def depth_quality(self) -> DepthQuality:
        from .protocol import BLS_DEPTH_MIN_MM, BLS_DEPTH_MAX_MM

        if self.depth_mm == 0:
            return DepthQuality.NONE
        if self.depth_mm < BLS_DEPTH_MIN_MM:
            return DepthQuality.TOO_SHALLOW
        if self.depth_mm > BLS_DEPTH_MAX_MM:
            return DepthQuality.TOO_DEEP
        return DepthQuality.GOOD


@dataclass(frozen=True)
class CompressionEvent:
    """Per-compression event summary from characteristic 0x0028.

    Emitted once when a compression is completed (depth returns to baseline).

    Attributes:
        timestamp: Device timestamp matching the real-time data stream.
        peak_depth_raw: Encoded peak depth (scaling differs from real-time mm).
        duration_raw: Timing metric.
        position_raw: Position/displacement metric.
        flags: Status flags.
        raw: Original 12-byte payload.
    """

    timestamp: int
    peak_depth_raw: int
    duration_raw: int
    position_raw: int
    flags: int
    raw: bytes

    @classmethod
    def from_bytes(cls, data: bytes) -> Optional[CompressionEvent]:
        """Parse a 12-byte notification payload.

        Format::

            Offset  Size  Type     Description
            0       2     uint16   Timestamp (LE)
            2       2     uint16   Reserved
            4       2     uint16   Peak depth (LE, encoded)
            6       2     uint16   Duration / timing (LE)
            8       2     uint16   Position / displacement (LE)
            10      2     uint16   Flags (LE)
        """
        if len(data) < 12:
            return None
        ts = int.from_bytes(data[0:2], "little")
        peak = int.from_bytes(data[4:6], "little")
        dur = int.from_bytes(data[6:8], "little")
        pos = int.from_bytes(data[8:10], "little")
        flags = int.from_bytes(data[10:12], "little")
        return cls(
            timestamp=ts,
            peak_depth_raw=peak,
            duration_raw=dur,
            position_raw=pos,
            flags=flags,
            raw=bytes(data),
        )


@dataclass
class Compression:
    """A completed compression detected by peak analysis of real-time samples.

    Attributes:
        wall_time: Wall clock time (seconds since session start).
        peak_depth_mm: Maximum depth reached during this compression.
        duration_ms: Duration from start to end of compression in milliseconds.
        event: Matching event summary from 0x0028, if received.
    """

    wall_time: float
    peak_depth_mm: int
    duration_ms: int
    event: Optional[CompressionEvent] = None

    @property
    def depth_quality(self) -> DepthQuality:
        from .protocol import BLS_DEPTH_MIN_MM, BLS_DEPTH_MAX_MM

        if self.peak_depth_mm < BLS_DEPTH_MIN_MM:
            return DepthQuality.TOO_SHALLOW
        if self.peak_depth_mm > BLS_DEPTH_MAX_MM:
            return DepthQuality.TOO_DEEP
        return DepthQuality.GOOD


@dataclass
class SessionStats:
    """Cumulative statistics for a CPR monitoring session.

    Attributes:
        duration_s: Session duration in seconds.
        total_compressions: Total number of compressions detected.
        avg_depth_mm: Average peak depth across all compressions.
        min_depth_mm: Minimum peak depth.
        max_depth_mm: Maximum peak depth.
        avg_rate_per_min: Average compression rate (compressions/minute).
        correct_depth_pct: Percentage of compressions in 50-60 mm range.
        depth_quality: Overall depth quality assessment.
        rate_quality: Overall rate quality assessment.
    """

    duration_s: float = 0.0
    total_compressions: int = 0
    avg_depth_mm: float = 0.0
    min_depth_mm: int = 0
    max_depth_mm: int = 0
    avg_rate_per_min: float = 0.0
    correct_depth_pct: float = 0.0
    depth_quality: DepthQuality = DepthQuality.NONE
    rate_quality: RateQuality = RateQuality.UNKNOWN
    compressions: list[Compression] = field(default_factory=list)

    @classmethod
    def from_compressions(
        cls, compressions: list[Compression], duration_s: float
    ) -> SessionStats:
        from .protocol import (
            BLS_DEPTH_MIN_MM,
            BLS_DEPTH_MAX_MM,
            BLS_RATE_MIN,
            BLS_RATE_MAX,
        )

        if not compressions:
            return cls(duration_s=duration_s, compressions=compressions)

        peaks = [c.peak_depth_mm for c in compressions]
        avg = sum(peaks) / len(peaks)
        good = sum(1 for p in peaks if BLS_DEPTH_MIN_MM <= p <= BLS_DEPTH_MAX_MM)

        rate = 0.0
        if len(compressions) >= 2:
            span = compressions[-1].wall_time - compressions[0].wall_time
            if span > 0:
                rate = (len(compressions) - 1) / span * 60

        if avg < BLS_DEPTH_MIN_MM:
            dq = DepthQuality.TOO_SHALLOW
        elif avg > BLS_DEPTH_MAX_MM:
            dq = DepthQuality.TOO_DEEP
        else:
            dq = DepthQuality.GOOD

        if rate == 0:
            rq = RateQuality.UNKNOWN
        elif rate < BLS_RATE_MIN:
            rq = RateQuality.TOO_SLOW
        elif rate > BLS_RATE_MAX:
            rq = RateQuality.TOO_FAST
        else:
            rq = RateQuality.GOOD

        return cls(
            duration_s=duration_s,
            total_compressions=len(compressions),
            avg_depth_mm=avg,
            min_depth_mm=min(peaks),
            max_depth_mm=max(peaks),
            avg_rate_per_min=rate,
            correct_depth_pct=good / len(peaks) * 100,
            depth_quality=dq,
            rate_quality=rq,
            compressions=compressions,
        )
