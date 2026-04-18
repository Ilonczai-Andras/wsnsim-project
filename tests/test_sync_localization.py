"""Unit tesztek — sync_localization modul (ClockDrift, RSSILocalizer).

Teszt osztályok
---------------
TestClockDriftZero      — nulla drift esetei
TestClockDriftPositive  — pozitív drift: siet az óra
TestClockDriftNegative  — negatív drift: késik az óra
TestClockSync           — sync_to() viselkedése
TestRSSILocalizer       — rssi_to_distance, estimate, localization_error
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from wsnsim.models.channel import LogDistanceChannel
from wsnsim.models.sync_localization import ClockDrift, RSSILocalizer


# ---------------------------------------------------------------------------
# Segédfüggvények / fixturák
# ---------------------------------------------------------------------------


def make_channel(sigma_db: float = 0.0, seed: int = 0) -> LogDistanceChannel:
    """Tipikus beltéri csatorna (n=2.7, d0=1 m, tx=0 dBm)."""
    return LogDistanceChannel(
        n=2.7,
        pl0_db=55.0,
        d0_m=1.0,
        sigma_db=sigma_db,
        tx_power_dbm=0.0,
        noise_floor_dbm=-100.0,
        rng=np.random.default_rng(seed),
    )


def make_localizer(sigma_db: float = 0.0, seed: int = 42) -> RSSILocalizer:
    return RSSILocalizer(
        channel=make_channel(sigma_db=sigma_db),
        rng=np.random.default_rng(seed),
    )


# Nem-kollineáris anchor háromszög + extra anchor
ANCHORS_3 = [(0.0, 0.0), (50.0, 0.0), (0.0, 50.0)]
ANCHORS_4 = [(0.0, 0.0), (50.0, 0.0), (0.0, 50.0), (50.0, 50.0)]
TRUE_POS = (25.0, 25.0)


def true_rssi(anchors, pos, ch=None):
    if ch is None:
        ch = make_channel()
    return [
        ch.rssi_dbm(math.sqrt((ax - pos[0]) ** 2 + (ay - pos[1]) ** 2))
        for ax, ay in anchors
    ]


# ---------------------------------------------------------------------------
# TestClockDriftZero
# ---------------------------------------------------------------------------


class TestClockDriftZero:
    def test_zero_drift_local_time_equals_sim(self):
        cd = ClockDrift(drift_ppm=0.0)
        for t in [0.0, 1000.0, 1_000_000.0, 1e9]:
            assert cd.local_time(t) == pytest.approx(t)

    def test_zero_drift_clock_error_is_zero(self):
        cd = ClockDrift(drift_ppm=0.0)
        for t in [0.0, 500.0, 1_000_000.0]:
            assert cd.clock_error_us(t) == pytest.approx(0.0)

    def test_default_offset_is_zero(self):
        cd = ClockDrift(drift_ppm=0.0)
        assert cd.offset_us == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# TestClockDriftPositive
# ---------------------------------------------------------------------------


class TestClockDriftPositive:
    def test_50ppm_at_1s(self):
        """50 ppm drift, 1 s → clock_error ≈ +50 µs."""
        cd = ClockDrift(drift_ppm=50.0)
        assert cd.clock_error_us(1_000_000.0) == pytest.approx(50.0, abs=1e-9)

    def test_100ppm_at_10ms(self):
        """100 ppm drift, 10 000 µs → clock_error ≈ +1 µs."""
        cd = ClockDrift(drift_ppm=100.0)
        assert cd.clock_error_us(10_000.0) == pytest.approx(1.0, abs=1e-9)

    def test_positive_drift_local_time_greater(self):
        cd = ClockDrift(drift_ppm=30.0)
        t = 500_000.0
        assert cd.local_time(t) > t


# ---------------------------------------------------------------------------
# TestClockDriftNegative
# ---------------------------------------------------------------------------


class TestClockDriftNegative:
    def test_minus_50ppm_at_1s(self):
        """−50 ppm drift, 1 s → clock_error ≈ −50 µs."""
        cd = ClockDrift(drift_ppm=-50.0)
        assert cd.clock_error_us(1_000_000.0) == pytest.approx(-50.0, abs=1e-9)

    def test_negative_drift_local_time_less(self):
        cd = ClockDrift(drift_ppm=-30.0)
        t = 500_000.0
        assert cd.local_time(t) < t


# ---------------------------------------------------------------------------
# TestClockSync
# ---------------------------------------------------------------------------


class TestClockSync:
    def test_sync_eliminates_error_at_sync_point(self):
        """sync_to(t) után clock_error_us(t) ≈ 0."""
        cd = ClockDrift(drift_ppm=50.0)
        t_sync = 2_000_000.0
        cd.sync_to(t_sync)
        assert cd.clock_error_us(t_sync) == pytest.approx(0.0, abs=1e-9)

    def test_sync_only_changes_offset(self):
        """sync_to() nem változtatja a drift_ppm-et."""
        cd = ClockDrift(drift_ppm=75.0)
        cd.sync_to(1_000_000.0)
        assert cd.drift_ppm == pytest.approx(75.0)

    def test_drift_accumulates_after_sync(self):
        """Szinkronizáció után t > t_sync esetén a drift újra akkumulálódik."""
        cd = ClockDrift(drift_ppm=50.0)
        t_sync = 1_000_000.0
        cd.sync_to(t_sync)
        # A szinkronizáció után 1 s-sel: újabb ~50 µs hiba keletkezik
        t_later = t_sync + 1_000_000.0
        error = cd.clock_error_us(t_later)
        assert abs(error) > 1.0   # nem nulla: drift fennáll


# ---------------------------------------------------------------------------
# TestRSSILocalizer
# ---------------------------------------------------------------------------


class TestRSSILocalizer:
    def test_rssi_to_distance_at_d0(self):
        """A referencia-távolságon (d=d0=1 m) rssi_to_distance visszaadja d0-t."""
        loc = make_localizer()
        ch = make_channel()
        rssi_at_d0 = ch.rssi_dbm(ch.d0_m)
        d_est = loc.rssi_to_distance(rssi_at_d0)
        assert d_est == pytest.approx(ch.d0_m, abs=0.01)

    def test_rssi_to_distance_monotone(self):
        """Távolabb → kisebb RSSI → nagyobb becsült d."""
        loc = make_localizer()
        ch = make_channel()
        d1, d2 = 10.0, 30.0
        rssi1 = ch.rssi_dbm(d1)
        rssi2 = ch.rssi_dbm(d2)
        assert loc.rssi_to_distance(rssi1) < loc.rssi_to_distance(rssi2)

    def test_rssi_to_distance_clamp_max(self):
        """Nagyon gyenge RSSI → klippelés 200.0 m-re."""
        loc = make_localizer()
        d_est = loc.rssi_to_distance(-300.0)   # extrém gyenge jel
        assert d_est == pytest.approx(200.0)

    def test_rssi_to_distance_clamp_min(self):
        """Nagyon erős RSSI → klippelés d0-ra."""
        loc = make_localizer()
        ch = make_channel()
        d_est = loc.rssi_to_distance(50.0)   # tx_power_dbm fölött
        assert d_est == pytest.approx(ch.d0_m)

    def test_estimate_3_anchors_no_noise(self):
        """3 anchor, zaj nélkül → |error| < 0.5 m."""
        loc = make_localizer()
        rssi = true_rssi(ANCHORS_3, TRUE_POS)
        x_est, y_est = loc.estimate(ANCHORS_3, rssi)
        err = math.sqrt((x_est - TRUE_POS[0]) ** 2 + (y_est - TRUE_POS[1]) ** 2)
        assert err < 0.5

    def test_estimate_4_anchors_overdetermined(self):
        """4 anchor (overdetermined), zaj nélkül → |error| < 1.0 m."""
        loc = make_localizer()
        rssi = true_rssi(ANCHORS_4, TRUE_POS)
        x_est, y_est = loc.estimate(ANCHORS_4, rssi)
        err = math.sqrt((x_est - TRUE_POS[0]) ** 2 + (y_est - TRUE_POS[1]) ** 2)
        assert err < 1.0

    def test_estimate_fewer_than_3_anchors_raises(self):
        """Kevesebb mint 3 anchor → ValueError."""
        loc = make_localizer()
        with pytest.raises(ValueError, match="3"):
            loc.estimate([(0.0, 0.0), (10.0, 0.0)], [-60.0, -65.0])

    def test_estimate_1_anchor_raises(self):
        loc = make_localizer()
        with pytest.raises(ValueError):
            loc.estimate([(0.0, 0.0)], [-60.0])

    def test_localization_error_zero_noise_small(self):
        """sigma=0 dB → mean_error < 0.5 m."""
        loc = make_localizer()
        err = loc.localization_error(ANCHORS_4, TRUE_POS, noise_sigma_db=0.0, n_trials=50)
        assert err < 0.5

    def test_localization_error_increases_with_noise(self):
        """Nagyobb zaj → nagyobb lokalizációs hiba."""
        loc_low = make_localizer(seed=42)
        loc_high = make_localizer(seed=42)
        err_low = loc_low.localization_error(ANCHORS_4, TRUE_POS, noise_sigma_db=2.0, n_trials=100)
        err_high = loc_high.localization_error(ANCHORS_4, TRUE_POS, noise_sigma_db=10.0, n_trials=100)
        assert err_high > err_low

    def test_localization_deterministic(self):
        """Ugyanaz a seed → azonos mean_error."""
        def run() -> float:
            loc = RSSILocalizer(channel=make_channel(), rng=np.random.default_rng(99))
            return loc.localization_error(ANCHORS_4, TRUE_POS, noise_sigma_db=4.0, n_trials=50)

        assert run() == pytest.approx(run())
