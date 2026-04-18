"""Unit tesztek a wsnsim.models.security modulhoz.

Teszteli a SecurityOverheadConfig konstansokat, a SecurityOverheadModel.apply()
és overhead számítások helyességét, valamint a ReplayProtection elfogadási logikáját
és állapotkezelését, beleértve egy abuse-case negatív tesztet is.
"""

from __future__ import annotations

import pytest

from wsnsim.models.energy import EnergyModel, EnergyState
from wsnsim.models.packet import Packet
from wsnsim.models.security import (
    OVERHEAD_MAC_ENCRYPT,
    OVERHEAD_MAC_ONLY,
    OVERHEAD_NONE,
    ReplayProtection,
    SecurityOverheadConfig,
    SecurityOverheadModel,
)


# ---------------------------------------------------------------------------
# Segédfüggvény
# ---------------------------------------------------------------------------

def _make_packet(size_bytes: int = 32) -> Packet:
    return Packet(packet_id=1, src=1, dst=0, size_bytes=size_bytes)


def _make_model(config: SecurityOverheadConfig) -> SecurityOverheadModel:
    return SecurityOverheadModel(config, EnergyModel())


# ---------------------------------------------------------------------------
# TestSecurityOverheadConfig
# ---------------------------------------------------------------------------

class TestSecurityOverheadConfig:
    """SecurityOverheadConfig konstansok és overhead_energy_j ellenőrzése."""

    def test_overhead_none_all_zero(self) -> None:
        """OVERHEAD_NONE: minden érték nulla (vagy nulla overhead)."""
        assert OVERHEAD_NONE.mic_bytes == 0
        assert OVERHEAD_NONE.encrypt_bytes == 0
        assert OVERHEAD_NONE.cpu_overhead_us == 0.0

    def test_overhead_mac_only_mic_nonzero(self) -> None:
        """OVERHEAD_MAC_ONLY: mic_bytes > 0."""
        assert OVERHEAD_MAC_ONLY.mic_bytes > 0

    def test_overhead_mac_only_no_encryption(self) -> None:
        """OVERHEAD_MAC_ONLY: encrypt_bytes == 0."""
        assert OVERHEAD_MAC_ONLY.encrypt_bytes == 0

    def test_overhead_mac_encrypt_has_encryption(self) -> None:
        """OVERHEAD_MAC_ENCRYPT: encrypt_bytes > 0."""
        assert OVERHEAD_MAC_ENCRYPT.encrypt_bytes > 0

    def test_overhead_mac_encrypt_has_mic(self) -> None:
        """OVERHEAD_MAC_ENCRYPT: mic_bytes > 0."""
        assert OVERHEAD_MAC_ENCRYPT.mic_bytes > 0

    def test_overhead_energy_j_matches_formula(self) -> None:
        """overhead_energy_j() kézi számítással egyezik: cpu_overhead_us * energy_per_us_j."""
        model = _make_model(OVERHEAD_MAC_ONLY)
        expected = OVERHEAD_MAC_ONLY.cpu_overhead_us * OVERHEAD_MAC_ONLY.energy_per_us_j
        assert model.overhead_energy_j() == pytest.approx(expected)

    def test_overhead_none_energy_zero(self) -> None:
        """OVERHEAD_NONE-nál overhead_energy_j() == 0.0."""
        model = _make_model(OVERHEAD_NONE)
        assert model.overhead_energy_j() == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# TestSecurityOverheadModelApply
# ---------------------------------------------------------------------------

class TestSecurityOverheadModelApply:
    """SecurityOverheadModel.apply() méret- és energiaszámítás."""

    def test_apply_size_mac_only(self) -> None:
        """apply() utáni size_bytes = eredeti + mic_bytes."""
        pkt = _make_packet(32)
        model = _make_model(OVERHEAD_MAC_ONLY)
        secured = model.apply(pkt, at_us=0.0)
        expected = 32 + OVERHEAD_MAC_ONLY.mic_bytes + OVERHEAD_MAC_ONLY.encrypt_bytes
        assert secured.size_bytes == expected

    def test_apply_size_mac_encrypt(self) -> None:
        """apply() utáni size_bytes = eredeti + mic_bytes + encrypt_bytes."""
        pkt = _make_packet(32)
        model = _make_model(OVERHEAD_MAC_ENCRYPT)
        secured = model.apply(pkt, at_us=0.0)
        expected = 32 + OVERHEAD_MAC_ENCRYPT.mic_bytes + OVERHEAD_MAC_ENCRYPT.encrypt_bytes
        assert secured.size_bytes == expected

    def test_apply_size_none_unchanged(self) -> None:
        """OVERHEAD_NONE esetén a csomag mérete nem változik."""
        pkt = _make_packet(32)
        model = _make_model(OVERHEAD_NONE)
        secured = model.apply(pkt, at_us=0.0)
        assert secured.size_bytes == 32

    def test_apply_size_bits_correct(self) -> None:
        """apply() utáni size_bits = size_bytes * 8."""
        pkt = _make_packet(32)
        model = _make_model(OVERHEAD_MAC_ONLY)
        secured = model.apply(pkt, at_us=0.0)
        assert secured.size_bits == secured.size_bytes * 8

    def test_apply_energy_consumed_increases(self) -> None:
        """EnergyModel consumed_j nő az apply() hívás után (cpu_overhead_us > 0)."""
        em = EnergyModel()
        em.flush(0.0)
        before = em.consumed_j
        model = SecurityOverheadModel(OVERHEAD_MAC_ONLY, em)
        model.apply(_make_packet(), at_us=0.0)
        assert em.consumed_j > before

    def test_apply_energy_none_unchanged(self) -> None:
        """OVERHEAD_NONE esetén consumed_j nem nő az apply() hívástól."""
        em = EnergyModel()
        em.flush(0.0)
        before = em.consumed_j
        model = SecurityOverheadModel(OVERHEAD_NONE, em)
        model.apply(_make_packet(), at_us=0.0)
        assert em.consumed_j == pytest.approx(before)

    def test_apply_preserves_packet_ids(self) -> None:
        """apply() megtartja a packet_id, src, dst értékeket."""
        pkt = Packet(packet_id=42, src=3, dst=7, size_bytes=20)
        model = _make_model(OVERHEAD_MAC_ONLY)
        secured = model.apply(pkt, at_us=0.0)
        assert secured.packet_id == 42
        assert secured.src == 3
        assert secured.dst == 7


# ---------------------------------------------------------------------------
# TestReplayProtectionBasic
# ---------------------------------------------------------------------------

class TestReplayProtectionBasic:
    """ReplayProtection alapvető elfogadási logika."""

    def test_first_seq_accepted(self) -> None:
        """Első seq=1 accept() → True."""
        rp = ReplayProtection()
        assert rp.accept(src=0, seq=1) is True

    def test_same_seq_rejected(self) -> None:
        """Ugyanaz a seq=1 • másodszor accept() → False (replay)."""
        rp = ReplayProtection()
        rp.accept(src=0, seq=1)
        assert rp.accept(src=0, seq=1) is False

    def test_higher_seq_accepted(self) -> None:
        """seq=2 az 1 után accept() → True."""
        rp = ReplayProtection()
        rp.accept(src=0, seq=1)
        assert rp.accept(src=0, seq=2) is True

    def test_lower_seq_rejected(self) -> None:
        """seq=0 (< last=1) accept() → False."""
        rp = ReplayProtection()
        rp.accept(src=0, seq=1)
        assert rp.accept(src=0, seq=0) is False

    def test_last_seq_updated(self) -> None:
        """last_seq() frissül elfogadott seq után."""
        rp = ReplayProtection()
        rp.accept(src=0, seq=5)
        assert rp.last_seq(0) == 5

    def test_last_seq_none_for_unknown(self) -> None:
        """last_seq() → None ismeretlen src esetén."""
        rp = ReplayProtection()
        assert rp.last_seq(99) is None


# ---------------------------------------------------------------------------
# TestReplayProtectionMultiSender
# ---------------------------------------------------------------------------

class TestReplayProtectionMultiSender:
    """Több küldő egymástól független állapotban."""

    def test_two_senders_independent(self) -> None:
        """src=0 és src=1 own seq-t fogadnak el egymástól függetlenül."""
        rp = ReplayProtection()
        assert rp.accept(src=0, seq=1) is True
        assert rp.accept(src=1, seq=1) is True  # src=1 független

    def test_src0_replay_does_not_affect_src1(self) -> None:
        """src=0 replay-je nem befolyásolja src=1 elfogadását."""
        rp = ReplayProtection()
        rp.accept(src=0, seq=1)
        rp.accept(src=1, seq=1)
        assert rp.accept(src=0, seq=1) is False  # src=0 replay
        assert rp.accept(src=1, seq=2) is True   # src=1 érintetlen

    def test_reset_single_src(self) -> None:
        """reset(src=0) után src=0 újra elfogad azonos seq-t, src=1 érintetlen."""
        rp = ReplayProtection()
        rp.accept(src=0, seq=3)
        rp.accept(src=1, seq=3)
        rp.reset(src=0)
        assert rp.accept(src=0, seq=3) is True   # reset után elfogad
        assert rp.accept(src=1, seq=3) is False  # src=1 érintetlen (seq=3 → replay)

    def test_reset_all(self) -> None:
        """reset() (src=None) után minden küldő állapota törlődik."""
        rp = ReplayProtection()
        rp.accept(src=0, seq=5)
        rp.accept(src=1, seq=7)
        rp.reset()
        assert rp.last_seq(0) is None
        assert rp.last_seq(1) is None


# ---------------------------------------------------------------------------
# TestAbuseCase
# ---------------------------------------------------------------------------

class TestAbuseCase:
    """Abuse-case tesztek: védelem nélkül és védelemmel."""

    def test_without_protection_replay_goes_unnoticed(self) -> None:
        """Negatív teszt: ReplayProtection nélkül egy egyszerű dict
        ugyanazt a (src, seq) párt kétszer is elfogadja.

        Ez a baseline dokumentálja, miért szükséges a védelemöszintű
        ReplayProtection — egy naiv megközelítés (dict) nem akadályozza
        meg a visszajátszást.
        """
        # Naiv implementáció: csak az utolsó látott seq-t tárolja
        naive_seen: dict[int, int] = {}  # src -> last_seq (de nem rejiciál!)

        def naive_accept(src: int, seq: int) -> bool:
            # Nem ellenőriz — minden csomagot "elfogad"
            naive_seen[src] = seq
            return True

        assert naive_accept(src=0, seq=1) is True
        # Visszajátszás: ugyanaz a seq — naiv implementáció ELFOGADJA
        assert naive_accept(src=0, seq=1) is True  # ← biztonsági rés

    def test_with_protection_replay_rejected(self) -> None:
        """Pozitív teszt: ReplayProtection-nel a visszajátszott seq elutasításra kerül."""
        rp = ReplayProtection()
        rp.accept(src=0, seq=1)
        # Visszajátszás elutasítva
        assert rp.accept(src=0, seq=1) is False

    def test_reset_enables_reuse(self) -> None:
        """reset() után az ugyanolyan seq újra elfogadható (pl. csomópont újraindítás)."""
        rp = ReplayProtection()
        rp.accept(src=0, seq=10)
        assert rp.accept(src=0, seq=10) is False  # replay
        rp.reset(src=0)
        assert rp.accept(src=0, seq=10) is True   # reset után újra elfogadva
