"""Unit tesztek — Megbízhatóság / ARQ (ARQConfig, ARQLink, ARQStats).

Teszt osztályok
---------------
TestARQConfig        — ARQConfig default és egyedi paraméterek.
TestARQLinkSuccess   — PRR≈1.0 esetén első kísérletbe siker.
TestARQLinkRetry     — PRR≈0.44 esetén retryk, determinizmus.
TestARQLinkDrop      — PRR≈0.0 esetén összes kísérlet sikertelen.
TestARQStats         — add(), pdr(), mean_attempts(), mean_energy_j().
"""

from __future__ import annotations

import numpy as np
import pytest

from wsnsim.models.channel import LogDistanceChannel
from wsnsim.models.energy import EnergyModel
from wsnsim.models.mac import Medium
from wsnsim.models.packet import Packet
from wsnsim.models.reliability import ARQConfig, ARQLink, ARQResult, ARQStats


# ---------------------------------------------------------------------------
# Segédfüggvények
# ---------------------------------------------------------------------------


def make_link(
    distance_m: float = 5.0,
    sigma_db: float = 0.0,
    retry_limit: int = 3,
    seed: int = 42,
    ch_seed: int = 0,
) -> ARQLink:
    """Friss ARQLink példány determinisztikus RNG-vel."""
    channel = LogDistanceChannel(sigma_db=sigma_db, rng=np.random.default_rng(ch_seed))
    return ARQLink(
        src=0,
        dst=1,
        channel=channel,
        energy_src=EnergyModel(node_id=0),
        energy_dst=EnergyModel(node_id=1),
        medium=Medium(),
        distance_m=distance_m,
        config=ARQConfig(retry_limit=retry_limit),
        rng=np.random.default_rng(seed),
    )


def make_packet(pid: int = 1) -> Packet:
    return Packet(packet_id=pid, src=0, dst=1, size_bytes=32)


# ---------------------------------------------------------------------------
# TestARQConfig
# ---------------------------------------------------------------------------


class TestARQConfig:
    def test_defaults(self):
        cfg = ARQConfig()
        assert cfg.retry_limit == 3
        assert cfg.ack_timeout_us == pytest.approx(10_000.0)
        assert cfg.backoff_base_us == pytest.approx(5_000.0)
        assert cfg.backoff_factor == pytest.approx(2.0)
        assert cfg.ack_size_bytes == 5

    def test_custom_values(self):
        cfg = ARQConfig(retry_limit=5, ack_timeout_us=20_000.0, backoff_factor=3.0)
        assert cfg.retry_limit == 5
        assert cfg.ack_timeout_us == pytest.approx(20_000.0)
        assert cfg.backoff_factor == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# TestARQLinkSuccess  — PRR ≈ 1.0 (d=5 m, sigma=0)
# ---------------------------------------------------------------------------


class TestARQLinkSuccess:
    """d=5 m, sigma_db=0 → PRR praktikusan 1.0 → első kísérletbe kézbesítve."""

    def test_success_on_first_attempt(self):
        link = make_link(distance_m=5.0)
        result = link.transmit(make_packet(), at_us=0.0)
        assert result.success
        assert result.attempts == 1

    def test_packet_delivered(self):
        link = make_link(distance_m=5.0)
        pkt = make_packet()
        result = link.transmit(pkt, at_us=0.0)
        assert pkt.delivered
        assert not pkt.lost

    def test_energy_positive(self):
        link = make_link(distance_m=5.0)
        result = link.transmit(make_packet(), at_us=0.0)
        assert result.energy_j > 0.0

    def test_total_tx_us_positive(self):
        link = make_link(distance_m=5.0)
        result = link.transmit(make_packet(), at_us=0.0)
        assert result.total_tx_us > 0.0

    def test_final_pkt_is_same_object(self):
        link = make_link(distance_m=5.0)
        pkt = make_packet()
        result = link.transmit(pkt, at_us=0.0)
        assert result.final_pkt is pkt


# ---------------------------------------------------------------------------
# TestARQLinkRetry  — PRR ≈ 0.44 (d=20 m, sigma=0)
# ---------------------------------------------------------------------------


class TestARQLinkRetry:
    """d=20 m, sigma_db=0 → PRR≈0.44 → vegyes eredmény, retryk lehetségesek."""

    def test_attempts_in_valid_range(self):
        """Minden egyes csomaghoz az attempts 1..retry_limit+1 között van."""
        link = make_link(distance_m=20.0, retry_limit=5)
        current_us = 0.0
        for i in range(15):
            pkt = make_packet(i)
            r = link.transmit(pkt, at_us=current_us)
            assert 1 <= r.attempts <= 5 + 1  # retry_limit + 1 total
            current_us += r.total_tx_us + 1_000.0

    def test_retries_do_occur(self):
        """Legalább néhány csomag megkezdése után előfordul retry (attempts > 1)."""
        link = make_link(distance_m=20.0, retry_limit=10, seed=7)
        current_us = 0.0
        attempts_list = []
        for i in range(30):
            pkt = make_packet(i)
            r = link.transmit(pkt, at_us=current_us)
            attempts_list.append(r.attempts)
            current_us += r.total_tx_us + 1_000.0
        assert max(attempts_list) > 1, "Legalább egy csomagnak kellett újraküldés"

    def test_determinism_same_seed(self):
        """Ugyanaz a seed → azonos eredmény-sorozat."""

        def run(seed: int) -> list[tuple[bool, int]]:
            link = make_link(distance_m=20.0, retry_limit=5, seed=seed)
            current_us = 0.0
            out = []
            for i in range(8):
                r = link.transmit(make_packet(i), at_us=current_us)
                out.append((r.success, r.attempts))
                current_us += r.total_tx_us + 1_000.0
            return out

        assert run(42) == run(42)

    def test_different_seed_may_differ(self):
        """Különböző seed → valószínűleg eltérő sorrend (sanity check)."""

        def run(seed: int) -> list[int]:
            link = make_link(distance_m=20.0, retry_limit=5, seed=seed)
            current_us = 0.0
            out = []
            for i in range(10):
                r = link.transmit(make_packet(i), at_us=current_us)
                out.append(r.attempts)
                current_us += r.total_tx_us + 1_000.0
            return out

        # Három különböző seed — nagyon valószínű, hogy legalább egy pár eltér
        results = [run(s) for s in [0, 1, 2]]
        assert any(results[0] != results[i] for i in range(1, 3))


# ---------------------------------------------------------------------------
# TestARQLinkDrop  — PRR ≈ 0.0 (d=40 m, sigma=0)
# ---------------------------------------------------------------------------


class TestARQLinkDrop:
    """d=40 m, sigma_db=0 → PRR≈0 → összes kísérlet sikertelen."""

    def test_success_false(self):
        link = make_link(distance_m=40.0, retry_limit=3)
        result = link.transmit(make_packet(), at_us=0.0)
        assert not result.success

    def test_attempts_equals_total_possible(self):
        """retry_limit=3 → 4 total kísérlet, mind sikertelen."""
        cfg = ARQConfig(retry_limit=3)
        link = make_link(distance_m=40.0, retry_limit=3)
        result = link.transmit(make_packet(), at_us=0.0)
        assert result.attempts == cfg.retry_limit + 1

    def test_packet_lost(self):
        link = make_link(distance_m=40.0, retry_limit=3)
        pkt = make_packet()
        link.transmit(pkt, at_us=0.0)
        assert pkt.lost
        assert not pkt.delivered

    def test_energy_still_consumed(self):
        """Sikertelen esetben is történt TX → energia > 0."""
        link = make_link(distance_m=40.0, retry_limit=3)
        result = link.transmit(make_packet(), at_us=0.0)
        assert result.energy_j > 0.0

    def test_drop_deterministic(self):
        """Két futtatás azonos seed-del azonos drop-eredményt ad."""
        def run() -> ARQResult:
            return make_link(distance_m=40.0, retry_limit=3, seed=42).transmit(
                make_packet(), at_us=0.0
            )

        r1, r2 = run(), run()
        assert r1.success == r2.success
        assert r1.attempts == r2.attempts
        assert r1.total_tx_us == pytest.approx(r2.total_tx_us)
        assert r1.energy_j == pytest.approx(r2.energy_j)


# ---------------------------------------------------------------------------
# TestARQStats
# ---------------------------------------------------------------------------


class TestARQStats:
    def _fill_stats(self, n_success: int, n_fail: int) -> ARQStats:
        """Feltölt egy ARQStats-ot szintetikus eredményekkel."""
        pkt = make_packet()
        stats = ARQStats()
        for _ in range(n_success):
            stats.add(ARQResult(success=True, attempts=2, total_tx_us=9000.0,
                                energy_j=0.001, final_pkt=pkt))
        for _ in range(n_fail):
            stats.add(ARQResult(success=False, attempts=4, total_tx_us=60000.0,
                                energy_j=0.004, final_pkt=pkt))
        return stats

    def test_empty_stats(self):
        s = ARQStats()
        assert s.total_packets == 0
        assert s.pdr() == pytest.approx(0.0)
        assert s.mean_attempts() == pytest.approx(0.0)
        assert s.mean_energy_j() == pytest.approx(0.0)

    def test_total_packets(self):
        s = self._fill_stats(3, 2)
        assert s.total_packets == 5

    def test_pdr_all_success(self):
        s = self._fill_stats(5, 0)
        assert s.pdr() == pytest.approx(1.0)

    def test_pdr_all_fail(self):
        s = self._fill_stats(0, 4)
        assert s.pdr() == pytest.approx(0.0)

    def test_pdr_mixed(self):
        s = self._fill_stats(3, 1)  # 3 sikeres, 1 sikertelen
        assert s.pdr() == pytest.approx(0.75)

    def test_mean_attempts(self):
        # 3×(attempts=2) + 1×(attempts=4) → mean = (6+4)/4 = 2.5
        s = self._fill_stats(3, 1)
        assert s.mean_attempts() == pytest.approx(2.5)

    def test_mean_energy_j(self):
        # 3×0.001 + 1×0.004 → mean = 0.007/4 = 0.00175
        s = self._fill_stats(3, 1)
        assert s.mean_energy_j() == pytest.approx(0.00175)

    def test_add_with_real_link(self):
        """Valós ARQLink-kel gyűjtött eredmények statisztikája konzisztens."""
        link = make_link(distance_m=5.0, retry_limit=3)
        stats = ARQStats()
        current_us = 0.0
        for i in range(20):
            pkt = make_packet(i)
            r = link.transmit(pkt, at_us=current_us)
            stats.add(r)
            current_us += r.total_tx_us + 1_000.0
        assert stats.total_packets == 20
        assert stats.pdr() == pytest.approx(1.0)    # d=5m → mindig sikerül
        assert stats.mean_energy_j() > 0.0
