"""StatsCollector — alapszintű statisztika-gyűjtő a szimulátorhoz.

Az összegyűjtött adatok típusonként (event_type) csoportosítva tárolódnak.
Minden rekord tartalmazza a szimulációs időpontot és egy opcionális numerikus
értéket (pl. üzenet mérete, energiafogyasztás).

Példa::

    from wsnsim.metrics.collector import StatsCollector
    from wsnsim.sim import SimClock, Scheduler

    clock = SimClock()
    stats = StatsCollector(clock)
    stats.record("tx", value=42.0)
    print(stats.summary())
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Record:
    """Egyetlen statisztikai rekord.

    Args:
        sim_time: A rögzítés szimulációs időpontja (µs).
        value:    Opcionális numerikus adat (pl. csomag mérete bájtban).
        tag:      Opcionális szöveges cimke a finomabb szűréshez.
    """

    sim_time: float
    value: float = 0.0
    tag: str = ""


class StatsCollector:
    """Szimulációs statisztika-gyűjtő.

    Típusonként (``event_type``) csoportosítva tárolja a rekordokat,
    és összesítő statisztikákat számít (db, összeg, átlag, min, max).

    Args:
        clock: A szimulációs óra, amelyből az időbélyeg olvasódik.
               Ha ``None``, a rekordba ``0.0`` kerül.

    Example:
        >>> from wsnsim.sim.clock import SimClock
        >>> clock = SimClock()
        >>> sc = StatsCollector(clock)
        >>> sc.record("tx", value=10.0)
        >>> sc.record("tx", value=20.0)
        >>> sc.record("rx", value=5.0)
        >>> sc.count("tx")
        2
        >>> sc.mean("tx")
        15.0
    """

    def __init__(self, clock: Optional[object] = None) -> None:
        self._clock = clock
        self._data: dict[str, list[Record]] = defaultdict(list)
        self._wall_start: float = time.monotonic()
        self._wall_end: Optional[float] = None

    # ---------------------------------------------------------------------------
    # Rögzítés
    # ---------------------------------------------------------------------------

    def record(
        self,
        event_type: str,
        value: float = 0.0,
        tag: str = "",
    ) -> None:
        """Egyetlen rekordot rögzít.

        Args:
            event_type: Az esemény kategóriája (pl. ``"tx"``, ``"rx"``).
            value:      Opcionális numerikus adat.
            tag:        Opcionális szöveges cimke.
        """
        sim_time = float(self._clock.now) if self._clock is not None else 0.0
        self._data[event_type].append(Record(sim_time=sim_time, value=value, tag=tag))

    def mark_end(self) -> None:
        """Rögzíti a futás befejezésének valós idejét (wall clock)."""
        self._wall_end = time.monotonic()

    # ---------------------------------------------------------------------------
    # Lekérdezők
    # ---------------------------------------------------------------------------

    def count(self, event_type: str) -> int:
        """Az adott típusú rekordok száma.

        Args:
            event_type: Az esemény kategóriája.

        Returns:
            Rekordok száma (0, ha nincs ilyen típus).
        """
        return len(self._data.get(event_type, []))

    def total(self, event_type: str) -> float:
        """Az adott típusú rekordok ``value`` mezőinek összege.

        Args:
            event_type: Az esemény kategóriája.

        Returns:
            Összeg, vagy 0.0 ha nincs rekord.
        """
        records = self._data.get(event_type, [])
        return sum(r.value for r in records)

    def mean(self, event_type: str) -> float:
        """Az adott típusú rekordok ``value`` mezőinek átlaga.

        Args:
            event_type: Az esemény kategóriája.

        Returns:
            Átlag, vagy 0.0 ha nincs rekord.
        """
        records = self._data.get(event_type, [])
        if not records:
            return 0.0
        return sum(r.value for r in records) / len(records)

    def minimum(self, event_type: str) -> float:
        """Az adott típusú rekordok minimum értéke.

        Args:
            event_type: Az esemény kategóriája.

        Returns:
            Minimum érték, vagy 0.0 ha nincs rekord.
        """
        records = self._data.get(event_type, [])
        return min((r.value for r in records), default=0.0)

    def maximum(self, event_type: str) -> float:
        """Az adott típusú rekordok maximum értéke.

        Args:
            event_type: Az esemény kategóriája.

        Returns:
            Maximum érték, vagy 0.0 ha nincs rekord.
        """
        records = self._data.get(event_type, [])
        return max((r.value for r in records), default=0.0)

    @property
    def event_types(self) -> list[str]:
        """Az összes rögzített eseménytípus neve."""
        return list(self._data.keys())

    @property
    def wall_elapsed(self) -> float:
        """A valós futási idő másodpercben (wall clock)."""
        end = self._wall_end if self._wall_end is not None else time.monotonic()
        return end - self._wall_start

    # ---------------------------------------------------------------------------
    # Összesítő
    # ---------------------------------------------------------------------------

    def summary(self) -> dict[str, dict[str, float]]:
        """Visszaad egy összesítő szótárt minden eseménytípusra.

        Returns:
            Szótár, amelynek kulcsai az eseménytípusok, értékei pedig
            a ``count``, ``total``, ``mean``, ``min``, ``max`` mezőket
            tartalmazó szótárak.
        """
        result: dict[str, dict[str, float]] = {}
        for etype, records in self._data.items():
            values = [r.value for r in records]
            result[etype] = {
                "count": float(len(values)),
                "total": sum(values),
                "mean": sum(values) / len(values) if values else 0.0,
                "min": min(values, default=0.0),
                "max": max(values, default=0.0),
            }
        return result

    def table_str(self) -> str:
        """Emberbarát szöveges táblázat az összesítőről.

        Returns:
            Formázott ASCII táblázat.
        """
        rows = self.summary()
        if not rows:
            return "(nincs adat)"

        header = f"{'Típus':<20} {'db':>6} {'összeg':>10} {'átlag':>10} {'min':>10} {'max':>10}"
        sep = "-" * len(header)
        lines = [sep, header, sep]
        for etype, s in sorted(rows.items()):
            lines.append(
                f"{etype:<20} {s['count']:>6.0f} {s['total']:>10.3f}"
                f" {s['mean']:>10.3f} {s['min']:>10.3f} {s['max']:>10.3f}"
            )
        lines.append(sep)
        lines.append(f"Valós futási idő: {self.wall_elapsed * 1000:.2f} ms")
        return "\n".join(lines)

    def __repr__(self) -> str:
        total_records = sum(len(v) for v in self._data.values())
        return f"StatsCollector(types={len(self._data)}, records={total_records})"
