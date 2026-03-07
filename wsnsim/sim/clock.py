"""SimClock — a szimulációs idő kezelése.

Az idő egysége mikroszekundum (µs), float típusban tárolva.
"""

from __future__ import annotations


class SimClock:
    """Egyszálú szimulációs óra, amely az aktuális szimulációs időt tárolja.

    Az idő egysége mikroszekundum (µs).  Az óra csak előre haladhat;
    visszalépési kísérlet :class:`ValueError`-t dob.

    Args:
        initial_time: Kiindulási időpont µs-ban (alapértelmezés: 0.0).

    Example:
        >>> clock = SimClock()
        >>> clock.now
        0.0
        >>> clock.advance(100.0)
        >>> clock.now
        100.0
    """

    def __init__(self, initial_time: float = 0.0) -> None:
        if initial_time < 0:
            raise ValueError(
                f"Az initial_time nem lehet negatív, kapott: {initial_time}"
            )
        self._time: float = float(initial_time)

    @property
    def now(self) -> float:
        """Az aktuális szimulációs idő µs-ban."""
        return self._time

    def advance(self, time: float) -> None:
        """Az órát *time* µs-ra állítja.

        Args:
            time: Az új szimulációs időpont µs-ban.

        Raises:
            ValueError: Ha *time* kisebb, mint az aktuális idő (visszalépés).
        """
        if time < self._time:
            raise ValueError(
                f"Az idő nem léphet vissza: {time} < {self._time}"
            )
        self._time = float(time)

    def reset(self, time: float = 0.0) -> None:
        """Visszaállítja az órát a megadott időpontra (csak tesztelési célra).

        Args:
            time: A visszaállítás célértéke µs-ban (alapértelmezés: 0.0).
        """
        if time < 0:
            raise ValueError(
                f"Az initial_time nem lehet negatív, kapott: {time}"
            )
        self._time = float(time)

    def __repr__(self) -> str:
        return f"SimClock(now={self._time:.3f}µs)"
