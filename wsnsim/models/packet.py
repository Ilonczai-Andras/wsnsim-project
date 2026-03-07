"""Packet — egyetlen rádiós csomag adatmodellje.

A ``Packet`` dataclass tartalmazza a csomag azonosítóját, méretét,
küldő/fogadó csomópontját, létrehozási és kézbesítési időpontját,
valamint jelzőbiteket a veszteség és ütközés jelölésére.

Példa::

    p = Packet(packet_id=1, src=0, dst=255, size_bytes=32)
    print(p.size_bits)  # 256
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Packet:
    """Egyetlen rádiós adatcsomag.

    Args:
        packet_id:    Egyedi azonosító.
        src:          Forrás csomópont azonosítója.
        dst:          Cél csomópont azonosítója (255 = broadcast).
        size_bytes:   Hasznos adat + fejléc mérete bájtban.
        created_at:   Létrehozás szimulációs időpontja (µs). Default: 0.0.
        delivered_at: Kézbesítés szimulációs időpontja (µs). None = még nem kézbesített.
        lost:         Igaz, ha a csomag elveszett a csatornán.
        collided:     Igaz, ha ütközés miatt dobódott el.

    Example:
        >>> p = Packet(packet_id=1, src=0, dst=1, size_bytes=32)
        >>> p.size_bits
        256
        >>> p.delivered
        False
    """

    packet_id: int
    src: int
    dst: int
    size_bytes: int = 32
    created_at: float = 0.0
    delivered_at: Optional[float] = field(default=None, compare=False)
    lost: bool = field(default=False, compare=False)
    collided: bool = field(default=False, compare=False)

    @property
    def size_bits(self) -> int:
        """A csomag mérete bitekben (``size_bytes * 8``)."""
        return self.size_bytes * 8

    @property
    def delivered(self) -> bool:
        """Igaz, ha a csomag sikeresen kézbesítve lett (``delivered_at`` nem None és nem lost)."""
        return self.delivered_at is not None and not self.lost

    @property
    def latency_us(self) -> Optional[float]:
        """Végponttól végpontig tartó késleltetés µs-ban, vagy None ha nem kézbesített."""
        if self.delivered_at is None:
            return None
        return self.delivered_at - self.created_at

    def __repr__(self) -> str:
        return (
            f"Packet(id={self.packet_id}, {self.src}→{self.dst}, "
            f"{self.size_bytes}B, delivered={self.delivered})"
        )
