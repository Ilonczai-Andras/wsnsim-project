"""Unit tesztek a LogDistanceChannel csatornamodellhez.

Tesztelt viselkedések:
  1. path_loss_db monoton növekszik a távolsággal.
  2. d=d0 esetén path_loss_db == pl0_db (shadowing=False).
  3. rssi_dbm = tx_power_dbm - path_loss_db.
  4. PRR monoton csökken a távolsággal.
  5. PRR ∈ [0, 1] minden távolságra.
  6. Shadowing seed-del reprodukálható.
  7. Kézi számítással való validálás (2 számpélda).
  8. Packet dataclass viselkedése.
"""

from __future__ import annotations

import math
import pytest
import numpy as np

from wsnsim.models.channel import LogDistanceChannel
from wsnsim.models.packet import Packet


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def ch_no_shadow() -> LogDistanceChannel:
    """Csatorna shadowing nélkül (determinisztikus)."""
    return LogDistanceChannel(
        n=2.7,
        pl0_db=55.0,
        d0_m=1.0,
        sigma_db=0.0,
        tx_power_dbm=0.0,
        noise_floor_dbm=-95.0,
        rng=np.random.default_rng(0),
    )


@pytest.fixture()
def ch_with_shadow() -> LogDistanceChannel:
    """Csatorna log-normal shadowing zajjal (σ=4 dB)."""
    return LogDistanceChannel(
        n=2.7,
        pl0_db=55.0,
        d0_m=1.0,
        sigma_db=4.0,
        tx_power_dbm=0.0,
        noise_floor_dbm=-95.0,
        rng=np.random.default_rng(42),
    )


# ---------------------------------------------------------------------------
# 1. Path loss — referencia-pont és monotonicitás
# ---------------------------------------------------------------------------


class TestPathLoss:
    """A path loss képlet helyes viselkedése."""

    def test_path_loss_at_d0_equals_pl0(self, ch_no_shadow: LogDistanceChannel) -> None:
        """d=d0 esetén PL(d0) == pl0_db (log10(1) = 0 → nincs korrekció)."""
        pl = ch_no_shadow.path_loss_db(ch_no_shadow.d0_m, shadowing=False)
        assert pl == pytest.approx(ch_no_shadow.pl0_db)

    def test_path_loss_increases_with_distance(self, ch_no_shadow: LogDistanceChannel) -> None:
        """A path loss monoton növekszik a távolsággal."""
        distances = [1.0, 5.0, 10.0, 20.0, 50.0, 100.0]
        pl_values = [ch_no_shadow.path_loss_db(d) for d in distances]
        for a, b in zip(pl_values, pl_values[1:]):
            assert a < b, f"PL nem monoton: PL({distances[pl_values.index(a)]}m)={a:.2f} > PL(...)={b:.2f}"

    def test_path_loss_manual_10m(self, ch_no_shadow: LogDistanceChannel) -> None:
        """Kézi számítás: PL(10m) = 55 + 10*2.7*log10(10/1) = 55 + 27.0 = 82.0 dB."""
        expected = 55.0 + 10 * 2.7 * math.log10(10.0 / 1.0)
        result = ch_no_shadow.path_loss_db(10.0, shadowing=False)
        assert result == pytest.approx(expected, rel=1e-6)

    def test_path_loss_manual_50m(self, ch_no_shadow: LogDistanceChannel) -> None:
        """Kézi számítás: PL(50m) = 55 + 10*2.7*log10(50) ≈ 55 + 45.88 = 100.88 dB."""
        expected = 55.0 + 10 * 2.7 * math.log10(50.0 / 1.0)
        result = ch_no_shadow.path_loss_db(50.0, shadowing=False)
        assert result == pytest.approx(expected, rel=1e-6)

    def test_path_loss_clips_below_d0(self, ch_no_shadow: LogDistanceChannel) -> None:
        """d < d0 esetén d0-ra klippelődik (nem ad negatív path loss-t)."""
        pl_at_d0 = ch_no_shadow.path_loss_db(ch_no_shadow.d0_m)
        pl_below = ch_no_shadow.path_loss_db(0.01)  # << d0
        assert pl_below == pytest.approx(pl_at_d0)


# ---------------------------------------------------------------------------
# 2. RSSI
# ---------------------------------------------------------------------------


class TestRSSI:
    """RSSI = Ptx - PL."""

    def test_rssi_equals_tx_minus_pl(self, ch_no_shadow: LogDistanceChannel) -> None:
        """RSSI(d) = tx_power_dbm - path_loss_db(d)."""
        for d in (1.0, 10.0, 50.0):
            expected = ch_no_shadow.tx_power_dbm - ch_no_shadow.path_loss_db(d)
            assert ch_no_shadow.rssi_dbm(d) == pytest.approx(expected)

    def test_rssi_decreases_with_distance(self, ch_no_shadow: LogDistanceChannel) -> None:
        """Az RSSI csökken a távolsággal."""
        distances = [1.0, 10.0, 50.0, 100.0]
        rssi_values = [ch_no_shadow.rssi_dbm(d) for d in distances]
        for a, b in zip(rssi_values, rssi_values[1:]):
            assert a > b


# ---------------------------------------------------------------------------
# 3. PRR — tartomány és monotonicitás
# ---------------------------------------------------------------------------


class TestPRR:
    """PRR helyes tartomány és monotonicitás."""

    def test_prr_in_range(self, ch_no_shadow: LogDistanceChannel) -> None:
        """PRR ∈ [0, 1] minden távolságra."""
        for d in (0.1, 1.0, 10.0, 50.0, 200.0, 1000.0):
            p = ch_no_shadow.prr(d, n_bits=256)
            assert 0.0 <= p <= 1.0, f"PRR({d}m) = {p} — kívül esik [0,1]-en"

    def test_prr_decreases_with_distance(self, ch_no_shadow: LogDistanceChannel) -> None:
        """PRR szigorúan csökken a távolsággal (shadowing nélkül)."""
        distances = [1.0, 5.0, 15.0, 30.0, 60.0, 120.0]
        prr_values = [ch_no_shadow.prr(d, n_bits=256, shadowing=False) for d in distances]
        for a, b in zip(prr_values, prr_values[1:]):
            assert a >= b, f"PRR nem monoton csökkenő: {a:.4f} < {b:.4f}"

    def test_prr_near_1_at_short_distance(self, ch_no_shadow: LogDistanceChannel) -> None:
        """Közel van a forráshoz → PRR ≈ 1 (erős jel, alacsony hibaarány)."""
        assert ch_no_shadow.prr(1.0, n_bits=256) > 0.999

    def test_prr_near_0_at_large_distance(self, ch_no_shadow: LogDistanceChannel) -> None:
        """Nagyon messze → PRR ≈ 0 (gyenge jel, magas hibaarány)."""
        assert ch_no_shadow.prr(500.0, n_bits=256) < 0.01


# ---------------------------------------------------------------------------
# 4. Shadowing — reprodukálhatóság
# ---------------------------------------------------------------------------


class TestShadowing:
    """Shadowing seed-del reprodukálható és valóban véletlen."""

    def _collect_prr(self, seed: int, n: int = 20) -> list[float]:
        ch = LogDistanceChannel(sigma_db=4.0, rng=np.random.default_rng(seed))
        return [ch.prr(20.0, n_bits=256, shadowing=True) for _ in range(n)]

    def test_same_seed_same_prr_sequence(self) -> None:
        """Azonos seed → azonos PRR-sorozat."""
        run1 = self._collect_prr(42)
        run2 = self._collect_prr(42)
        assert run1 == run2

    def test_different_seeds_different_prr(self) -> None:
        """Eltérő seed → eltérő PRR-sorozat."""
        run_a = self._collect_prr(1)
        run_b = self._collect_prr(99)
        assert run_a != run_b

    def test_shadowing_adds_variability(self) -> None:
        """Shadowing esetén a PRR szórása pozitív (legalább néhány különböző érték)."""
        ch = LogDistanceChannel(sigma_db=6.0, rng=np.random.default_rng(0))
        values = [ch.prr(20.0, n_bits=256, shadowing=True) for _ in range(50)]
        # std > 0 → valóban változó
        assert np.std(values) > 0.001


# ---------------------------------------------------------------------------
# 5. Packet dataclass
# ---------------------------------------------------------------------------


class TestPacket:
    """A Packet dataclass helyes viselkedése."""

    def test_size_bits(self) -> None:
        """size_bits = size_bytes * 8."""
        p = Packet(packet_id=1, src=0, dst=1, size_bytes=32)
        assert p.size_bits == 256

    def test_not_delivered_by_default(self) -> None:
        """Alapból nem kézbesített."""
        p = Packet(packet_id=1, src=0, dst=1)
        assert not p.delivered
        assert p.latency_us is None

    def test_delivered_after_setting_delivered_at(self) -> None:
        """Ha delivered_at be van állítva, a csomag kézbesítettnek számít."""
        p = Packet(packet_id=1, src=0, dst=1, created_at=100.0, delivered_at=300.0)
        assert p.delivered
        assert p.latency_us == pytest.approx(200.0)

    def test_lost_flag_overrides_delivered(self) -> None:
        """Ha lost=True, delivered=False, még ha delivered_at is be van állítva."""
        p = Packet(packet_id=1, src=0, dst=1, delivered_at=300.0, lost=True)
        assert not p.delivered
