"""Scheduler — heapq-alapú eseménysor a diszkrét eseményű szimulátorhoz.

Az ütemező felel az események prioritásos sorba rendezéséért és
időrendi feldolgozásáért.  A véletlenszerűség kontrollálandó:
az opcionális *rng* paraméter egy ``numpy.random.default_rng(seed)``
generátor, amelyet külső kód adhat át.
"""

from __future__ import annotations

import heapq
from typing import Any, Callable, Optional

import numpy as np

from wsnsim.sim.clock import SimClock
from wsnsim.sim.event import Event


class Scheduler:
    """Eseményvezérelt ütemező heapq-alapú prioritásos sorral.

    Az ütemező a :class:`~wsnsim.sim.clock.SimClock`-ot automatikusan
    előre lépteti minden feldolgozott esemény időpontjára.

    Args:
        clock: A szimulátor közös órája.
        rng:   Opcionális NumPy véletlenszám-generátor
               (``numpy.random.default_rng(seed)``).  Ha None, akkor
               egy seed nélküli generátor jön létre, de reprodukálható
               futáshoz mindig adj meg seedet.

    Example:
        >>> clock = SimClock()
        >>> sched = Scheduler(clock, rng=np.random.default_rng(42))
        >>> results = []
        >>> sched.schedule(10.0, lambda e: results.append(e.payload), payload="A")
        Event(...)
        >>> sched.schedule(5.0,  lambda e: results.append(e.payload), payload="B")
        Event(...)
        >>> sched.run()
        2
        >>> results
        ['B', 'A']
    """

    def __init__(
        self,
        clock: SimClock,
        rng: Optional[np.random.Generator] = None,
    ) -> None:
        self._clock: SimClock = clock
        self._rng: np.random.Generator = (
            rng if rng is not None else np.random.default_rng()
        )
        self._queue: list[Event] = []
        self._seq: int = 0  # globális eseménysorszám — FIFO tie-breaker

    # ---------------------------------------------------------------------------
    # Ütemezés
    # ---------------------------------------------------------------------------

    def schedule(
        self,
        time: float,
        callback: Callable[[Event], None],
        payload: Any = None,
        priority: int = 0,
    ) -> Event:
        """Új eseményt vesz fel a sorba.

        Args:
            time:     Az esemény kívánt szimulációs időpontja (µs).
            callback: Függvény, amelyet az esemény feldolgozásakor hív meg
                      az ütemező.  Aláírása: ``callback(event: Event) -> None``.
            payload:  Tetszőleges adat, amelyet a callback kap meg.
            priority: Tie-breaker azonos *time* esetén; kisebb érték =
                      magasabb prioritás (alapértelmezés: 0).

        Returns:
            A létrehozott :class:`~wsnsim.sim.event.Event` objektum.

        Raises:
            ValueError: Ha *time* a jelenlegi szimulációs idő előtt van.
        """
        if time < self._clock.now:
            raise ValueError(
                f"Esemény a múltba nem ütemezhető: {time} < {self._clock.now}"
            )
        evt = Event(
            time=time,
            priority=priority,
            callback=callback,
            payload=payload,
            _seq=self._seq,
        )
        self._seq += 1
        heapq.heappush(self._queue, evt)
        return evt

    # ---------------------------------------------------------------------------
    # Futtatás
    # ---------------------------------------------------------------------------

    def step(self) -> Optional[Event]:
        """Feldolgozza a legközelebbi esedékes eseményt.

        Az óra az esemény időpontjára ugrik, majd a callback meghívódik.

        Returns:
            A feldolgozott esemény, vagy *None*, ha a sor üres.
        """
        if not self._queue:
            return None
        evt: Event = heapq.heappop(self._queue)
        self._clock.advance(evt.time)
        evt.callback(evt)
        return evt

    def run(self) -> int:
        """Az összes sorban lévő eseményt feldolgozza sorban.

        Returns:
            A feldolgozott események száma.
        """
        count = 0
        while self._queue:
            self.step()
            count += 1
        return count

    def run_until(self, end_time: float) -> int:
        """Az eseményeket *end_time* µs-ig (bezárólag) dolgozza fel.

        Args:
            end_time: A szimulációs időkorlát µs-ban.

        Returns:
            A feldolgozott események száma.
        """
        count = 0
        while self._queue and self._queue[0].time <= end_time:
            self.step()
            count += 1
        return count

    # ---------------------------------------------------------------------------
    # Lekérdezők
    # ---------------------------------------------------------------------------

    @property
    def is_empty(self) -> bool:
        """Igaz, ha nincs ütemezett esemény a sorban."""
        return len(self._queue) == 0

    @property
    def size(self) -> int:
        """A sorban várakozó események száma."""
        return len(self._queue)

    @property
    def rng(self) -> np.random.Generator:
        """A hozzárendelt NumPy véletlenszám-generátor."""
        return self._rng

    @property
    def clock(self) -> SimClock:
        """A hozzárendelt szimulációs óra."""
        return self._clock

    def __repr__(self) -> str:
        return (
            f"Scheduler(size={self.size}, clock={self._clock.now:.3f}µs)"
        )
