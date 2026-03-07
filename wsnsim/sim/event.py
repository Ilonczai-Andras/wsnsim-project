"""Event — az eseményvezérelt szimulátor esemény-struktúrája.

Egy esemény tartalmazza az ütemezett időpontot, prioritást (tie-breaker),
egy callback-et, amely az esemény bekövetkezésekor hívódik meg, és egy
tetszőleges payload-ot.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    pass  # körköros import elkerülésére


@dataclass(order=False)
class Event:
    """Egyetlen szimulációs esemény.

    Az események összehasonlítása az ``(time, priority, _seq)`` hármas
    alapján történik, ahol *priority* kisebb értéke magasabb prioritást
    jelent (tie-breaker azonos időpontú eseményeknél), *_seq* pedig a
    bekerülési sorrendet rögzíti (FIFO garantálásához).

    Args:
        time:     Az esemény ütemezett szimulációs időpontja (µs).
        priority: Tie-breaker azonos *time* esetén (kisebb = előbb). Default: 0.
        callback: Függvény, amelyet a Scheduler hív meg az esemény
                  feldolgozásakor.  Aláírása: ``callback(event: Event) -> None``.
        payload:  Tetszőleges adat, amelyet a callback megkap. Default: None.
        _seq:     Belső sorszám — ne állítsd be kézzel; a Scheduler kezeli.

    Example:
        >>> def handler(evt):
        ...     print(evt.payload)
        >>> e = Event(time=100.0, priority=0, callback=handler, payload="ping")
        >>> e.time
        100.0
    """

    time: float
    priority: int
    callback: Callable[["Event"], None]
    payload: Any = None
    _seq: int = field(default=0, compare=False, repr=False)

    # --- összehasonlítás -------------------------------------------------------

    def __lt__(self, other: "Event") -> bool:
        """Rendezési kulcs: (time, priority, _seq) — kisebb = hamarabb kerül sor."""
        return (self.time, self.priority, self._seq) < (
            other.time,
            other.priority,
            other._seq,
        )

    def __le__(self, other: "Event") -> bool:
        return (self.time, self.priority, self._seq) <= (
            other.time,
            other.priority,
            other._seq,
        )

    def __gt__(self, other: "Event") -> bool:
        return (self.time, self.priority, self._seq) > (
            other.time,
            other.priority,
            other._seq,
        )

    def __ge__(self, other: "Event") -> bool:
        return (self.time, self.priority, self._seq) >= (
            other.time,
            other.priority,
            other._seq,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Event):
            return NotImplemented
        return (self.time, self.priority, self._seq) == (
            other.time,
            other.priority,
            other._seq,
        )

    def __repr__(self) -> str:
        return (
            f"Event(time={self.time}µs, priority={self.priority}, "
            f"seq={self._seq}, payload={self.payload!r})"
        )
