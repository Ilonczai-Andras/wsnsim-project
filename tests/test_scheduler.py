"""Unit tesztek a Scheduler, SimClock és Event modulokhoz.

Tesztelt viselkedések:
  1. Az események időrendi sorrendben dolgozódnak fel (különböző időbélyegek).
  2. Azonos időbélyegű eseményeknél a prioritás (tie-breaker) érvényesül:
     kisebb priority érték = hamarabb kerül sorra.
  3. Azonos időbélyeg és prioritás esetén a bekerülési sorrend (FIFO) tartja
     meg a determinizmusát.
  4. A SimClock helyesen kezeli az előrehaladást és a visszalépési tilalmat.
  5. A Scheduler run_until() csak az időkorláton belüli eseményeket dolgozza fel.
  6. A véletlenszerűség deterministikusan reprodukálható numpy seeddel.
"""

from __future__ import annotations

import pytest
import numpy as np

from wsnsim.sim import SimClock, Event, Scheduler


# ---------------------------------------------------------------------------
# Segéd-fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def clock() -> SimClock:
    """Nulláról induló friss szimulációs óra."""
    return SimClock()


@pytest.fixture()
def sched(clock: SimClock) -> Scheduler:
    """Deterministikus Scheduler seed=0 RNG-vel."""
    return Scheduler(clock, rng=np.random.default_rng(0))


# ---------------------------------------------------------------------------
# 1. Esemény-időrend teszt
# ---------------------------------------------------------------------------


class TestEventOrdering:
    """Az események a szimulációs idő növekvő sorrendjében kerülnek feldolgozásra."""

    def test_events_processed_in_time_order(self, sched: Scheduler) -> None:
        """Különböző időbélyegű események időrendi sorrendben dolgozódnak fel."""
        processed: list[float] = []

        for t in (300.0, 100.0, 50.0, 200.0):
            sched.schedule(t, lambda e, _=None: processed.append(e.time))

        sched.run()

        assert processed == sorted(processed), (
            f"Az események nem időrendben futottak le: {processed}"
        )

    def test_clock_advances_monotonically(self, sched: Scheduler, clock: SimClock) -> None:
        """Az óra minden lépésnél monoton növekszik."""
        times: list[float] = []

        def capture(e: Event) -> None:
            times.append(clock.now)

        for t in (10.0, 5.0, 25.0, 15.0):
            sched.schedule(t, capture)

        sched.run()

        for a, b in zip(times, times[1:]):
            assert a <= b, f"Az óra visszalépett: {a} → {b}"

    def test_single_event_sets_clock(self, sched: Scheduler, clock: SimClock) -> None:
        """Egyetlen esemény feldolgozása után az óra az esemény időpontján áll."""
        sched.schedule(42.0, lambda e: None)
        sched.step()
        assert clock.now == pytest.approx(42.0)


# ---------------------------------------------------------------------------
# 2. Prioritás / tie-breaker teszt
# ---------------------------------------------------------------------------


class TestPriorityTieBreaker:
    """Azonos időbélyegű eseményeket a prioritás rendez — kisebb = előbb."""

    def test_lower_priority_runs_first(self, sched: Scheduler) -> None:
        """priority=0 megelőzi priority=10-et, ha az időbélyeg azonos."""
        order: list[int] = []

        sched.schedule(100.0, lambda e: order.append(e.payload), payload=10, priority=10)
        sched.schedule(100.0, lambda e: order.append(e.payload), payload=0,  priority=0)
        sched.schedule(100.0, lambda e: order.append(e.payload), payload=5,  priority=5)

        sched.run()

        assert order == [0, 5, 10], (
            f"Prioritásos sorrend hibás: {order}"
        )

    def test_negative_priority_runs_before_zero(self, sched: Scheduler) -> None:
        """Negatív prioritás még a priority=0 elé kerül."""
        order: list[int] = []

        sched.schedule(50.0, lambda e: order.append(e.payload), payload=0,   priority=0)
        sched.schedule(50.0, lambda e: order.append(e.payload), payload=-1,  priority=-1)

        sched.run()

        assert order == [-1, 0], f"Negatív prioritás nem előz: {order}"

    def test_fifo_within_same_time_and_priority(self, sched: Scheduler) -> None:
        """Ha az időbélyeg és a prioritás is azonos, a bekerülési sorrend (FIFO) érvényes."""
        order: list[str] = []

        for label in ("A", "B", "C"):
            sched.schedule(
                200.0,
                lambda e: order.append(e.payload),
                payload=label,
                priority=0,
            )

        sched.run()

        assert order == ["A", "B", "C"], (
            f"FIFO sorrend nem érvényesül: {order}"
        )


# ---------------------------------------------------------------------------
# 3. SimClock viselkedési tesztek
# ---------------------------------------------------------------------------


class TestSimClock:
    """A SimClock helyes működése."""

    def test_initial_time_is_zero(self) -> None:
        """Alapértelmezetten 0.0 µs-ról indul."""
        assert SimClock().now == pytest.approx(0.0)

    def test_advance_updates_clock(self) -> None:
        """Az advance() helyesen frissíti az aktuális időt."""
        c = SimClock()
        c.advance(123.456)
        assert c.now == pytest.approx(123.456)

    def test_advance_to_same_time_allowed(self) -> None:
        """Azonos időpontra való 'haladás' megengedett (nulla lépés)."""
        c = SimClock(100.0)
        c.advance(100.0)  # nem dob kivételt
        assert c.now == pytest.approx(100.0)

    def test_backward_time_raises(self) -> None:
        """Visszalépési kísérlet ValueError-t dob."""
        c = SimClock(50.0)
        with pytest.raises(ValueError, match="vissza"):
            c.advance(10.0)

    def test_negative_initial_time_raises(self) -> None:
        """Negatív kezdőidő ValueError-t dob."""
        with pytest.raises(ValueError):
            SimClock(-1.0)


# ---------------------------------------------------------------------------
# 4. run_until teszt
# ---------------------------------------------------------------------------


class TestRunUntil:
    """A run_until() csak az időkorláton belüli eseményeket dolgozza fel."""

    def test_run_until_stops_at_boundary(self, sched: Scheduler) -> None:
        """Az időkorláton kívüli esemény bent marad a sorban."""
        processed: list[float] = []

        for t in (10.0, 20.0, 30.0, 40.0):
            sched.schedule(t, lambda e: processed.append(e.time))

        sched.run_until(25.0)

        assert processed == [10.0, 20.0], f"Nem várt lista: {processed}"
        assert sched.size == 2, f"Maradék esemény száma hibás: {sched.size}"

    def test_run_until_inclusive_boundary(self, sched: Scheduler) -> None:
        """A pontosan a határon lévő esemény is feldolgozódik."""
        processed: list[float] = []

        sched.schedule(10.0, lambda e: processed.append(e.time))
        sched.run_until(10.0)

        assert processed == [10.0]
        assert sched.is_empty


# ---------------------------------------------------------------------------
# 5. Determinizmus / seed teszt
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Ugyanazon seed reprodukálható eredményt ad."""

    def _run_with_seed(self, seed: int) -> list[float]:
        clock = SimClock()
        rng = np.random.default_rng(seed)
        sched = Scheduler(clock, rng=rng)

        results: list[float] = []

        # Számos véletlen időpontú eseményt ütemezünk
        for _ in range(20):
            t = float(rng.integers(1, 1000))
            sched.schedule(t, lambda e: results.append(e.time))

        sched.run()
        return results

    def test_same_seed_same_output(self) -> None:
        """Rögzített seed esetén a szimulációs kimenet minden futásnál azonos."""
        run1 = self._run_with_seed(42)
        run2 = self._run_with_seed(42)
        assert run1 == run2

    def test_different_seeds_different_output(self) -> None:
        """Eltérő seedek (általában) eltérő kimenetet adnak."""
        run_a = self._run_with_seed(1)
        run_b = self._run_with_seed(2)
        # Statisztikailag gyakorlatilag lehetetlen, hogy 20 véletlenszám azonos legyen
        assert run_a != run_b
