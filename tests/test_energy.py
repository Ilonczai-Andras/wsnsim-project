"""Unit tesztek az EnergyModel és EnergyState modulhoz.

Tesztelt viselkedések:
  1. Állapotváltás után az elfogyasztott energia helyes (kézi számítás).
  2. Negatív energia guard: remaining_j soha nem negatív.
  3. Duty-cycle hatás: nagyobb active arány → nagyobb átlagos fogyasztás.
  4. Üzemidő-becslés: P×T = E összefüggés.
  5. Idővisszalépés ValueError-t dob.
  6. flush() az utolsó állapot fogyasztását is elszámolja.
  7. is_depleted és soc_percent helyes értéket adnak.
"""

from __future__ import annotations

import pytest

from wsnsim.models.energy import DEFAULT_POWER_MW, EnergyModel, EnergyState


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def em() -> EnergyModel:
    """Friss EnergyModel kis akkuval (könnyű lemeríteni tesztekben)."""
    return EnergyModel(battery_j=1.0, initial_state=EnergyState.SLEEP)


# ---------------------------------------------------------------------------
# 1. Energiaintegráció kézi számítással
# ---------------------------------------------------------------------------


class TestEnergyIntegration:
    """Az energiaintegráció kézileg ellenőrizhető értékeket ad."""

    def test_tx_1_second(self) -> None:
        """1 s TX fogyasztás: E = P_TX × 1 s = 52.2 mW × 1 s = 0.0522 J."""
        em = EnergyModel(battery_j=100.0, initial_state=EnergyState.TX)
        em.transition(EnergyState.SLEEP, at_us=1_000_000.0)   # 1 s
        expected = DEFAULT_POWER_MW[EnergyState.TX] * 1e-3 * 1.0
        assert em.consumed_j == pytest.approx(expected, rel=1e-6)

    def test_sleep_1_hour(self) -> None:
        """1 h SLEEP: E = 0.003 mW × 3600 s = 0.0000108 J."""
        em = EnergyModel(battery_j=100.0, initial_state=EnergyState.SLEEP)
        em.transition(EnergyState.SLEEP, at_us=3_600 * 1_000_000.0)
        expected = DEFAULT_POWER_MW[EnergyState.SLEEP] * 1e-3 * 3600.0
        assert em.consumed_j == pytest.approx(expected, rel=1e-4)

    def test_multiple_transitions_sum_correctly(self) -> None:
        """Több állapot fogyasztása összeadódik."""
        em = EnergyModel(battery_j=100.0, initial_state=EnergyState.IDLE)
        # 1 s IDLE
        em.transition(EnergyState.TX, at_us=1_000_000.0)
        # 0.5 s TX
        em.transition(EnergyState.SLEEP, at_us=1_500_000.0)

        e_idle  = DEFAULT_POWER_MW[EnergyState.IDLE] * 1e-3 * 1.0
        e_tx    = DEFAULT_POWER_MW[EnergyState.TX]   * 1e-3 * 0.5
        assert em.consumed_j == pytest.approx(e_idle + e_tx, rel=1e-6)

    def test_zero_duration_no_energy(self) -> None:
        """Nulla idejű állapot nem fogyaszt energiát."""
        em = EnergyModel(battery_j=100.0, initial_state=EnergyState.TX)
        em.transition(EnergyState.TX, at_us=0.0)
        assert em.consumed_j == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 2. Negatív energia guard
# ---------------------------------------------------------------------------


class TestNegativeEnergyGuard:
    """remaining_j soha nem negatív."""

    def test_remaining_never_negative(self, em: EnergyModel) -> None:
        """Még ha a fogyasztás meghaladja a kapacitást, remaining_j >= 0 marad."""
        # A kis akkut (1 J) "merítsük le": 1000 s TX → >> 1 J
        em.transition(EnergyState.TX, at_us=0.0)
        em.transition(EnergyState.SLEEP, at_us=1_000 * 1_000_000.0)
        assert em.remaining_j >= 0.0

    def test_consumed_clips_to_battery(self, em: EnergyModel) -> None:
        """consumed_j nem haladja meg a battery_j-t."""
        em.transition(EnergyState.TX, at_us=0.0)
        em.transition(EnergyState.SLEEP, at_us=1_000 * 1_000_000.0)
        assert em.consumed_j <= em.battery_j

    def test_is_depleted_when_empty(self, em: EnergyModel) -> None:
        """is_depleted igaz, ha a maradék energia nulla."""
        em.transition(EnergyState.TX, at_us=0.0)
        em.transition(EnergyState.SLEEP, at_us=1_000 * 1_000_000.0)
        assert em.is_depleted

    def test_not_depleted_when_fresh(self) -> None:
        """Friss akku: is_depleted hamis."""
        em = EnergyModel(battery_j=9720.0)
        assert not em.is_depleted
        assert em.soc_percent == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# 3. Duty-cycle hatás
# ---------------------------------------------------------------------------


class TestDutyCycle:
    """Nagyobb aktív arány → nagyobb átlagos fogyasztás."""

    def _avg_power(self, duty_cycle: float, duration_s: float = 10.0) -> float:
        """Szimulálja a megadott duty-cycle-t és visszaadja az átlagos fogyasztást.

        duty_cycle: az aktív (TX+RX) időarány 0…1 között.
        """
        em = EnergyModel(battery_j=99999.0, initial_state=EnergyState.SLEEP)
        t_us = 0.0
        slot_us = 10_000.0   # 10 ms-es slot
        n_slots = int(duration_s * 1e6 / slot_us)

        for _ in range(n_slots):
            active_us = slot_us * duty_cycle
            sleep_us  = slot_us - active_us

            # Aktív: TX fele, RX fele
            tx_us = active_us / 2.0
            rx_us = active_us / 2.0

            em.transition(EnergyState.TX,    at_us=t_us)
            t_us += tx_us
            em.transition(EnergyState.RX,    at_us=t_us)
            t_us += rx_us
            em.transition(EnergyState.SLEEP, at_us=t_us)
            t_us += sleep_us

        em.flush(t_us)
        return em.average_power_w(total_time_us=t_us)

    def test_higher_duty_cycle_higher_power(self) -> None:
        """Nagyobb duty-cycle → nagyobb átlagos fogyasztás."""
        p_low  = self._avg_power(0.01)
        p_mid  = self._avg_power(0.10)
        p_high = self._avg_power(0.50)
        assert p_low < p_mid < p_high, (
            f"Nem monoton: {p_low:.6f} < {p_mid:.6f} < {p_high:.6f} sérül"
        )

    def test_full_sleep_minimal_power(self) -> None:
        """100% SLEEP → átlagos fogyasztás ≈ P_SLEEP."""
        p = self._avg_power(0.0)
        assert p == pytest.approx(
            DEFAULT_POWER_MW[EnergyState.SLEEP] * 1e-3, rel=1e-3
        )

    def test_full_active_maximal_power(self) -> None:
        """100% TX/RX → átlagos fogyasztás ≈ (P_TX + P_RX) / 2."""
        p = self._avg_power(1.0)
        expected = (
            DEFAULT_POWER_MW[EnergyState.TX] + DEFAULT_POWER_MW[EnergyState.RX]
        ) / 2.0 * 1e-3
        assert p == pytest.approx(expected, rel=1e-3)


# ---------------------------------------------------------------------------
# 4. Üzemidő-becslés
# ---------------------------------------------------------------------------


class TestLifetimeEstimate:
    """Üzemidő-becslés helyes: T = E / P."""

    def test_lifetime_formula(self) -> None:
        """T_lifetime = remaining_j / avg_power_w."""
        em = EnergyModel(battery_j=100.0, initial_state=EnergyState.TX)
        em.transition(EnergyState.SLEEP, at_us=1_000_000.0)   # 1 s TX

        p = DEFAULT_POWER_MW[EnergyState.TX] * 1e-3
        expected_lifetime = em.remaining_j / p
        assert em.lifetime_estimate_s(avg_power_w=p) == pytest.approx(
            expected_lifetime, rel=1e-6
        )

    def test_lifetime_infinite_at_zero_power(self) -> None:
        """Nulla fogyasztásnál a becsült élettartam végtelen."""
        em = EnergyModel(battery_j=100.0)
        lt = em.lifetime_estimate_s(avg_power_w=0.0)
        assert lt == float("inf")


# ---------------------------------------------------------------------------
# 5. Idővisszalépés tilalma
# ---------------------------------------------------------------------------


class TestTimeMonotonicity:
    """Idővisszalépés ValueError-t dob."""

    def test_backward_time_raises(self) -> None:
        """Ha at_us < az előző váltás ideje, ValueError keletkezik."""
        em = EnergyModel(battery_j=100.0, initial_state=EnergyState.IDLE)
        em.transition(EnergyState.TX, at_us=1000.0)
        with pytest.raises(ValueError, match="tiltott"):
            em.transition(EnergyState.SLEEP, at_us=500.0)


# ---------------------------------------------------------------------------
# 6. flush()
# ---------------------------------------------------------------------------


class TestFlush:
    """flush() az utolsó állapot fogyasztását is elszámolja."""

    def test_flush_accumulates_energy(self) -> None:
        """flush() után consumed_j nagyobb, mint előtte."""
        em = EnergyModel(battery_j=100.0, initial_state=EnergyState.TX)
        before = em.consumed_j
        em.flush(at_us=500_000.0)   # 0.5 s TX
        assert em.consumed_j > before

    def test_flush_same_state_is_idempotent_at_same_time(self) -> None:
        """Kétszer flush() ugyanarra az időpontra nem ad hozzá energiát."""
        em = EnergyModel(battery_j=100.0, initial_state=EnergyState.TX)
        em.flush(at_us=500_000.0)
        after_first = em.consumed_j
        em.flush(at_us=500_000.0)
        assert em.consumed_j == pytest.approx(after_first)
