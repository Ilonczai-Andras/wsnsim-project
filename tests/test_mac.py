"""Unit tesztek — MAC protokoll modellek (ALOHA, CSMA, Medium).

Teszt osztályok
---------------
TestMedium           — közeg, regisztráció, ütközés-detektálás
TestALOHACollision   — pure ALOHA ütközési szcenáriók
TestCSMABackoff      — CSMA carrier-sense + BEB logika
TestDeterminism      — determinisztikus seed ellenőrzése
TestIntegration      — ALOHA vs CSMA összehasonlítás
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
import numpy as np

from wsnsim.models.mac import ALOHAMac, CSMAMac, Medium, TxResult
from wsnsim.models.packet import Packet


# ---------------------------------------------------------------------------
# Segédfüggvények
# ---------------------------------------------------------------------------


def pkt(pid: int, src: int = 1, dst: int = 0) -> Packet:
    """Egyszerű teszt-csomag."""
    return Packet(packet_id=pid, src=src, dst=dst)


# ---------------------------------------------------------------------------
# Medium tesztek
# ---------------------------------------------------------------------------


class TestMedium:
    def test_no_collision_single_tx(self):
        m = Medium()
        col = m.register_tx(1, 0.0, 4000.0)
        assert col is False

    def test_simultaneous_collision_detected(self):
        m = Medium()
        p1, p2 = pkt(1, src=1), pkt(2, src=2)
        m.register_tx(1, 0.0, 4000.0, p1)
        col = m.register_tx(2, 0.0, 4000.0, p2)
        assert col is True
        assert p1.collided  # retroaktívan jelölve
        assert p2.collided

    def test_sequential_txs_no_collision(self):
        m = Medium()
        p1, p2 = pkt(1, src=1), pkt(2, src=2)
        m.register_tx(1, 0.0, 4000.0, p1)
        col = m.register_tx(2, 4000.0, 8000.0, p2)
        assert col is False
        assert not p1.collided
        assert not p2.collided

    def test_partial_overlap_is_collision(self):
        """Részleges átfedés is ütközés."""
        m = Medium()
        p1, p2 = pkt(1, src=1), pkt(2, src=2)
        m.register_tx(1, 0.0, 4000.0, p1)
        col = m.register_tx(2, 2000.0, 6000.0, p2)
        assert col is True
        assert p1.collided
        assert p2.collided

    def test_is_busy_at(self):
        m = Medium()
        m.register_tx(1, 0.0, 4000.0)
        assert m.is_busy_at(0.0)
        assert m.is_busy_at(1999.0)
        assert not m.is_busy_at(4000.0)  # [0, 4000) → 4000 már szabad

    def test_busy_until_returns_end_time(self):
        m = Medium()
        m.register_tx(1, 0.0, 4000.0)
        assert m.busy_until(0.0) == 4000.0
        assert m.busy_until(4000.0) == 4000.0  # szabad → visszaadja at_us-t

    def test_exclude_node_ignores_own_tx(self):
        m = Medium()
        m.register_tx(1, 0.0, 4000.0)
        assert not m.is_busy_at(0.0, exclude_node=1)
        assert m.is_busy_at(0.0, exclude_node=2)  # csomópont 1 még ott van

    def test_has_collision_query(self):
        m = Medium()
        m.register_tx(1, 0.0, 4000.0)
        m.register_tx(2, 2000.0, 6000.0)
        assert m.has_collision(1)
        assert m.has_collision(2)

    def test_clear_removes_all_txs(self):
        m = Medium()
        m.register_tx(1, 0.0, 4000.0)
        m.clear()
        assert m.tx_count == 0
        assert not m.is_busy_at(0.0)

    def test_tx_count_property(self):
        m = Medium()
        m.register_tx(1, 0.0, 1000.0)
        m.register_tx(2, 5000.0, 6000.0)
        assert m.tx_count == 2


# ---------------------------------------------------------------------------
# Pure ALOHA tesztek
# ---------------------------------------------------------------------------


class TestALOHACollision:
    def test_single_sender_success(self):
        m = Medium()
        mac = ALOHAMac(medium=m, tx_duration_us=4000.0)
        p = pkt(1)
        r = mac.send(1, p, at_us=0.0)
        assert r.success
        assert not r.collision
        assert not p.collided

    def test_two_simultaneous_both_collide(self):
        """Két csomópont egyidőben küld → mindkettő ütközik."""
        m = Medium()
        mac = ALOHAMac(medium=m, tx_duration_us=4000.0)
        p1, p2 = pkt(1, src=1), pkt(2, src=2)
        mac.send(1, p1, at_us=0.0)
        mac.send(2, p2, at_us=0.0)
        assert p1.collided  # a Medium retroaktívan jelölte
        assert p2.collided

    def test_sequential_no_collision(self):
        m = Medium()
        mac = ALOHAMac(medium=m, tx_duration_us=4000.0)
        p1, p2 = pkt(1, src=1), pkt(2, src=2)
        r1 = mac.send(1, p1, at_us=0.0)
        r2 = mac.send(2, p2, at_us=4000.0)
        assert r1.success
        assert r2.success
        assert not p1.collided
        assert not p2.collided

    def test_partial_overlap_collision(self):
        m = Medium()
        mac = ALOHAMac(medium=m, tx_duration_us=4000.0)
        p1, p2 = pkt(1, src=1), pkt(2, src=2)
        mac.send(1, p1, at_us=0.0)
        mac.send(2, p2, at_us=2000.0)  # [2000, 6000) ∩ [0, 4000) ≠ ∅
        assert p1.collided
        assert p2.collided

    def test_tx_count_increments(self):
        m = Medium()
        mac = ALOHAMac(medium=m, tx_duration_us=4000.0)
        for i in range(5):
            mac.send(i, pkt(i), at_us=float(i) * 5000.0)
        assert mac.tx_count == 5

    def test_txresult_fields(self):
        m = Medium()
        mac = ALOHAMac(medium=m, tx_duration_us=4000.0)
        r = mac.send(1, pkt(1), at_us=100.0)
        assert r.retries == 0
        assert r.backoff_total_us == 0.0
        assert r.tx_start_us == 100.0
        assert not r.dropped


# ---------------------------------------------------------------------------
# CSMA + BEB tesztek
# ---------------------------------------------------------------------------


class TestCSMABackoff:
    def test_defers_when_channel_busy(self):
        """CSMA csomópont vár, ha csatorna foglalt; ütközésmentes adás."""
        m = Medium()
        csma = CSMAMac(medium=m, tx_duration_us=4000.0, slot_us=1000.0,
                       cw_min=4, cw_max=32, max_retries=5,
                       rng=np.random.default_rng(42))
        p1, p2 = pkt(1, src=1), pkt(2, src=2)
        r1 = csma.send(1, p1, at_us=0.0)
        r2 = csma.send(2, p2, at_us=0.0)  # csatorna foglalt → halasztás

        assert r1.success
        assert r2.success
        assert r2.tx_start_us >= 4000.0  # ≥ r1 vége
        assert not p1.collided
        assert not p2.collided

    def test_sequential_success_no_backoff(self):
        """Szekvenciális küldések nem igényelnek backoff-ot."""
        m = Medium()
        csma = CSMAMac(medium=m, tx_duration_us=1000.0,
                       rng=np.random.default_rng(0))
        packets = [pkt(i, src=i) for i in range(3)]
        results = [csma.send(i, packets[i], at_us=float(i) * 2000.0)
                   for i in range(3)]
        assert all(r.success for r in results)
        assert all(r.retries == 0 for r in results)
        assert all(not p.collided for p in packets)

    def test_three_simultaneous_serialize(self):
        """Három szimultán csomópont szerialization miatt mind sikeres."""
        m = Medium()
        csma = CSMAMac(medium=m, tx_duration_us=4000.0, slot_us=500.0,
                       cw_min=2, cw_max=16, max_retries=5,
                       rng=np.random.default_rng(7))
        packets = [pkt(i, src=i) for i in range(3)]
        results = [csma.send(i, packets[i], at_us=0.0) for i in range(3)]
        assert all(r.success for r in results)
        assert all(not p.collided for p in packets)
        # Adáskezdések nem átfedők
        starts = sorted(r.tx_start_us for r in results)
        for i in range(len(starts) - 1):
            assert starts[i + 1] >= starts[i] + 4000.0

    def test_max_retries_causes_drop(self):
        """Ha minden kísérlet ütközik (rejtett csomópont), a csomag eldobódik."""
        m = Medium()
        csma = CSMAMac(medium=m, tx_duration_us=4000.0, slot_us=1000.0,
                       cw_min=4, cw_max=16, max_retries=2,
                       rng=np.random.default_rng(0))
        p = pkt(1)
        # Minden register_tx-et sikerelen visszatérőre state-elünk (rejtett csomópont),
        # így a CSMA mindig ütközést észlel és végül elveti a csomagot.
        with patch.object(m, 'register_tx', return_value=True):
            r = csma.send(1, p, at_us=0.0)

        assert r.dropped
        assert not r.success
        assert r.retries == 2
        assert csma.drop_count == 1
        assert csma.collision_count == 3  # max_retries + 1 kísérlet

    def test_successful_retry_clears_collision_flag(self):
        """Sikeres újraküldés visszaállítja a csomag kollizió-jelzőjét."""
        m = Medium()
        # Első kísérletkor ütközik (előre regisztrált), második sikeres
        m.register_tx(99, 0.0, 100.0)   # blocker → A vár 100-ig
        m.register_tx(98, 100.0, 200.0) # ütközés @ t=100

        # max_retries=1 → lesz első (ütköző) és második (sikeres) kísérlet
        csma = CSMAMac(medium=m, tx_duration_us=100.0, slot_us=0.0,
                       cw_min=1, cw_max=1, max_retries=1,
                       rng=np.random.default_rng(0))
        p = pkt(10, src=10)
        r = csma.send(10, p, at_us=0.0)

        # Második kísérlet @ t=200 sikeres (semmi más ott)
        assert r.success
        assert not r.dropped
        assert not p.collided  # visszaállítva sikeres küldésnél


# ---------------------------------------------------------------------------
# Determinizmus tesztek
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_csma_same_seed_same_result(self):
        """Azonos seed → azonos backoff sorrend és tx_start_us értékek."""
        def run(seed: int) -> list[float]:
            m = Medium()
            # Kényszerített ütközés + backoff
            m.register_tx(99, 0.0, 4000.0)   # blocker
            m.register_tx(98, 4000.0, 8000.0) # második ütközés

            csma = CSMAMac(medium=m, tx_duration_us=4000.0, slot_us=1000.0,
                           cw_min=4, cw_max=32, max_retries=5,
                           rng=np.random.default_rng(seed))
            p = pkt(1)
            r = csma.send(1, p, at_us=0.0)
            return [r.tx_start_us, r.backoff_total_us, float(r.retries)]

        assert run(42) == run(42)

    def test_backoff_samples_seed_dependent(self):
        """Különböző seedek különböző backoff-mintákat adnak (cw=32 esetén)."""
        # Az RNG mintagenerálást közvetlenül ellenőrizzük
        samples = {int(np.random.default_rng(s).integers(0, 32)) for s in range(20)}
        assert len(samples) > 1  # 20 különböző seed → több különböző érték


# ---------------------------------------------------------------------------
# Integrációs / összehasonlító tesztek
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_aloha_vs_csma_collision_rate(self):
        """CSMA ütközési aránya kisebb, mint ALOHA-é nagy terhelésnél."""
        N = 8          # szimultán küldő
        ROUNDS = 200
        rng = np.random.default_rng(0)

        aloha_collisions = 0
        csma_collisions = 0

        for _ in range(ROUNDS):
            # ALOHA kör
            m_a = Medium()
            mac_a = ALOHAMac(medium=m_a, tx_duration_us=4000.0)
            pkts_a = [pkt(i, src=i) for i in range(N)]
            for i in range(N):
                mac_a.send(i, pkts_a[i], at_us=0.0)
            aloha_collisions += sum(1 for p in pkts_a if p.collided)

            # CSMA kör
            m_c = Medium()
            mac_c = CSMAMac(medium=m_c, tx_duration_us=4000.0,
                            slot_us=1000.0, cw_min=4, cw_max=32,
                            max_retries=5, rng=rng)
            pkts_c = [pkt(i, src=i) for i in range(N)]
            for i in range(N):
                mac_c.send(i, pkts_c[i], at_us=0.0)
            csma_collisions += sum(1 for p in pkts_c if p.collided)

        # ALOHA-nál N>=2 szimultán sender → mindenki ütközik
        aloha_rate = aloha_collisions / (N * ROUNDS)
        csma_rate = csma_collisions / (N * ROUNDS)

        assert aloha_rate > 0.9, f"ALOHA ütközési ráta váratlanul alacsony: {aloha_rate:.3f}"
        assert csma_rate < aloha_rate, (
            f"CSMA ({csma_rate:.3f}) nem jobb mint ALOHA ({aloha_rate:.3f})"
        )

    def test_medium_reuse_after_clear(self):
        """Medium.clear() után újrahasználható, korábbi state nem szivárog."""
        m = Medium()
        mac = ALOHAMac(medium=m, tx_duration_us=1000.0)

        # Első kör: ütközés
        p1, p2 = pkt(1, src=1), pkt(2, src=2)
        mac.send(1, p1, at_us=0.0)
        mac.send(2, p2, at_us=0.0)
        assert p1.collided

        # Törles után: clean state
        m.clear()
        p3 = pkt(3, src=3)
        r = mac.send(3, p3, at_us=0.0)
        assert r.success
        assert not p3.collided
