"""Biztonsági overhead modell WSN csomópontokhoz.

Ez a modul **nem** valódi kriptográfiát valósít meg — kizárólag a biztonsági
intézkedések kommunikációs és energetikai overheadjét modellezi:

* Extra bájtok (MIC/TAG + titkosított hasznos adat)
* CPU energia (MCU kriptó feldolgozási idő × teljesítmény)
* Latencia overhead (µs/csomag)

Három előre definiált konfig konstans érhető el:

* ``OVERHEAD_NONE``         — nincs biztonsági overhead (alap, referencia)
* ``OVERHEAD_MAC_ONLY``     — csak üzenet integritás (MIC/CBC-MAC), nincs titkosítás
* ``OVERHEAD_MAC_ENCRYPT``  — MIC + payload titkosítás (pl. AES-128-CCM)

A ``ReplayProtection`` osztály monoton szekvenciaszám-alapú visszajátszásvédelmet
modellezi, per-sender állapottal.

Példa::

    from wsnsim.models.security import (
        SecurityOverheadConfig,
        SecurityOverheadModel,
        ReplayProtection,
        OVERHEAD_NONE,
        OVERHEAD_MAC_ONLY,
        OVERHEAD_MAC_ENCRYPT,
    )
    from wsnsim.models.energy import EnergyModel, EnergyState
    from wsnsim.models.packet import Packet

    em = EnergyModel()
    model = SecurityOverheadModel(OVERHEAD_MAC_ONLY, em)
    pkt = Packet(packet_id=1, src=1, dst=0, size_bytes=32)
    secured = model.apply(pkt, at_us=0.0)
    print(secured.size_bytes)    # 32 + 8 = 40
    print(model.overhead_energy_j())  # 100.0 * 3e-6 = 3e-4 J

    rp = ReplayProtection()
    print(rp.accept(src=1, seq=1))  # True
    print(rp.accept(src=1, seq=1))  # False — replay
    print(rp.accept(src=1, seq=2))  # True
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from wsnsim.models.energy import EnergyModel, EnergyState
from wsnsim.models.packet import Packet


# ---------------------------------------------------------------------------
# SecurityOverheadConfig — konfig dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SecurityOverheadConfig:
    """Biztonsági overhead konfiguráció egy csomópontra.

    Attributes
    ----------
    mic_bytes:
        Message Integrity Code (MIC/TAG) hossza bájtban.
        0 = nincs integritásvédelem.
    encrypt_bytes:
        Titkosítással hozzáadott bájtok száma (pl. IV, padding) felső becslés.
        0 = nincs titkosítás.
    cpu_overhead_us:
        MCU kriptó feldolgozási idő µs/csomag (pl. AES-128 enkripció/dekripció).
    energy_per_us_j:
        Aktív MCU teljesítmény J/µs egységben (pl. CC2430: ~3e-6 J/µs ≈ 3 mW).
    """

    mic_bytes: int = 0
    encrypt_bytes: int = 0
    cpu_overhead_us: float = 0.0
    energy_per_us_j: float = 3e-6


# ---------------------------------------------------------------------------
# Előre definiált konfigok
# ---------------------------------------------------------------------------

#: Biztonsági overhead nélküli referencia konfig.
OVERHEAD_NONE: SecurityOverheadConfig = SecurityOverheadConfig(
    mic_bytes=0,
    encrypt_bytes=0,
    cpu_overhead_us=0.0,
    energy_per_us_j=3e-6,
)

#: Csak üzenet integritás (MIC/CBC-MAC, 8 bájtos tag), nincs titkosítás.
#: Tipikus: IEEE 802.15.4 MIC-64.
OVERHEAD_MAC_ONLY: SecurityOverheadConfig = SecurityOverheadConfig(
    mic_bytes=8,
    encrypt_bytes=0,
    cpu_overhead_us=100.0,
    energy_per_us_j=3e-6,
)

#: MIC + payload titkosítás (pl. AES-128-CCM: 8 B tag + 16 B overhead).
#: Tipikus: IEEE 802.15.4 ENC-MIC-128.
OVERHEAD_MAC_ENCRYPT: SecurityOverheadConfig = SecurityOverheadConfig(
    mic_bytes=8,
    encrypt_bytes=16,
    cpu_overhead_us=300.0,
    energy_per_us_j=3e-6,
)


# ---------------------------------------------------------------------------
# SecurityOverheadModel
# ---------------------------------------------------------------------------


class SecurityOverheadModel:
    """Biztonsági overhead modell egy WSN csomóponthoz.

    A ``apply()`` metódus egy új, megnövelt méretű ``Packet`` példányt ad vissza,
    és a CPU overhead energiát az ``EnergyModel``-en számolja el (IDLE állapot,
    ``cpu_overhead_us`` ideig).

    Parameters
    ----------
    config:
        A biztonsági overhead konfiguráció.
    energy:
        Az adott csomóponthoz tartozó ``EnergyModel`` példány.
    """

    def __init__(
        self,
        config: SecurityOverheadConfig,
        energy: EnergyModel,
    ) -> None:
        self._config = config
        self._energy = energy

    @property
    def config(self) -> SecurityOverheadConfig:
        """Az aktuális biztonsági overhead konfig."""
        return self._config

    def apply(self, packet: Packet, at_us: float = 0.0) -> Packet:
        """Alkalmazza a biztonsági overheadet egy csomagra.

        Visszaad egy új ``Packet`` példányt, amelynek ``size_bytes`` megnőtt
        ``mic_bytes + encrypt_bytes``-szal. Közben az ``EnergyModel``-en
        IDLE állapotban elszámolja a ``cpu_overhead_us`` feldolgozási időt.

        Parameters
        ----------
        packet:
            Az eredeti csomag.
        at_us:
            A szimulációs időpont, ahonnan a CPU overhead elszámolása indul.

        Returns
        -------
        Packet
            Új ``Packet`` példány megnövelt ``size_bytes``-szal.
        """
        extra_bytes = self._config.mic_bytes + self._config.encrypt_bytes
        new_size = packet.size_bytes + extra_bytes

        if self._config.cpu_overhead_us > 0.0:
            self._energy.flush(at_us)
            self._energy.transition(EnergyState.IDLE, at_us)
            self._energy.flush(at_us + self._config.cpu_overhead_us)

        return Packet(
            packet_id=packet.packet_id,
            src=packet.src,
            dst=packet.dst,
            size_bytes=new_size,
            created_at=packet.created_at,
            delivered_at=packet.delivered_at,
            lost=packet.lost,
            collided=packet.collided,
        )

    def overhead_energy_j(self) -> float:
        """Egyetlen csomagra jutó CPU overhead energiafogyasztás (J).

        Számítás: ``cpu_overhead_us × energy_per_us_j``.

        Returns
        -------
        float
            Overhead energia joulesban.
        """
        return self._config.cpu_overhead_us * self._config.energy_per_us_j

    def latency_overhead_us(self) -> float:
        """Egyetlen csomag feldolgozásának latencia overheadja (µs).

        Returns
        -------
        float
            Latencia overhead µs-ban (= ``cpu_overhead_us``).
        """
        return self._config.cpu_overhead_us


# ---------------------------------------------------------------------------
# ReplayProtection
# ---------------------------------------------------------------------------


class ReplayProtection:
    """Monoton szekvenciaszám alapú visszajátszás-védelem.

    Minden küldőhöz (``src``) a legutóbb elfogadott szekvenciaszámot tárolja.
    Egy csomag elfogadásra kerül, ha ``seq > last_seq[src]``; ellenkező esetben
    visszajátszásnak minősül és elutasításra kerül.

    Ez egy egyszerűsített modell: nem implementál sliding window-t, csak
    monoton növekvő szekvenciaszámot vár. Valódi rendszerben a szekvenciaszám
    wrapping-et és ablakos elfogadást is kezelni kellene.

    Parameters
    ----------
    window_size:
        Dokumentációs paraméter (interfész-kompatibilitásból); a jelenlegi
        implementáció nem használja — az egyszerű monoton modell elegendő
        a WSN simulátor szintjén.
    """

    def __init__(self, window_size: int = 32) -> None:
        self._window_size = window_size
        self._last: dict[int, int] = {}  # src -> last accepted seq

    def accept(self, src: int, seq: int) -> bool:
        """Elfogadás-döntés egy érkező csomag szekvenciaszámára.

        Elfogad (``True``), ha ``seq > last_seq[src]`` vagy ``src`` ismeretlen.
        Visszajátszásnak minősíti (``False``), ha ``seq <= last_seq[src]``.

        Parameters
        ----------
        src:
            A küldő csomópont azonosítója.
        seq:
            A csomag szekvenciaszáma.

        Returns
        -------
        bool
            ``True`` ha elfogadva, ``False`` ha visszajátszás.
        """
        last = self._last.get(src)
        if last is None or seq > last:
            self._last[src] = seq
            return True
        return False

    def reset(self, src: Optional[int] = None) -> None:
        """Az állapot törlése.

        Parameters
        ----------
        src:
            Ha megadva, csak az adott küldő állapota törlődik.
            Ha ``None``, az összes küldő állapota törlődik.
        """
        if src is None:
            self._last.clear()
        else:
            self._last.pop(src, None)

    def last_seq(self, src: int) -> Optional[int]:
        """Az adott küldőtől utoljára elfogadott szekvenciaszám.

        Parameters
        ----------
        src:
            A küldő csomópont azonosítója.

        Returns
        -------
        int | None
            Az utolsó elfogadott seq, vagy ``None`` ha még nem érkezett csomag.
        """
        return self._last.get(src)
