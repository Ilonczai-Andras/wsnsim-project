"""Megbízhatóság és ARQ — Stop-and-Wait ARQ modell WSN összeköttetésekhez.

Osztályok
---------
ARQConfig
    Konfigurációs dataclass: retry_limit, timeout, backoff paraméterek.
ARQResult
    Egy átviteli kísérlet immutábilis eredménye.
ARQLink
    Pont-pont összeköttetés Stop-and-Wait ARQ-val.
ARQStats
    Aggregált statisztika több átvitelhez.

Modellezési döntések
--------------------
* A ``retry_limit`` a maximális **újraküldések** számát jelöli (az első
  adást nem számolja bele). Tehát az összes lehetséges kísérlet száma
  ``retry_limit + 1``.
* Az ARQ-logika a DES scheduler nélkül, idő-lépéses módban fut —
  a szimulált idő monoton növekszik minden kísérlettel.
* Az ACK csomag adásideje arányos ``ARQConfig.ack_size_bytes / packet.size_bytes``
  és ``tx_duration_us``-szal (skálázott modell).
* Az energia-delta per csomag: forrás-node ``consumed_j``-jának változása
  az átvitel eleje és vége között.

Példa::

    import numpy as np
    from wsnsim.models.channel import LogDistanceChannel
    from wsnsim.models.energy import EnergyModel
    from wsnsim.models.mac import Medium
    from wsnsim.models.packet import Packet
    from wsnsim.models.reliability import ARQConfig, ARQLink, ARQStats

    ch  = LogDistanceChannel(sigma_db=0.0, rng=np.random.default_rng(0))
    rng = np.random.default_rng(42)
    link = ARQLink(
        src=0, dst=1,
        channel=ch,
        energy_src=EnergyModel(node_id=0),
        energy_dst=EnergyModel(node_id=1),
        medium=Medium(),
        distance_m=5.0,
        rng=rng,
    )
    pkt = Packet(packet_id=1, src=0, dst=1)
    result = link.transmit(pkt, at_us=0.0)
    assert result.success
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from wsnsim.models.channel import LogDistanceChannel
from wsnsim.models.energy import EnergyModel, EnergyState
from wsnsim.models.mac import Medium
from wsnsim.models.packet import Packet


# ---------------------------------------------------------------------------
# ARQConfig — konfigurációs paraméterek
# ---------------------------------------------------------------------------


@dataclass
class ARQConfig:
    """Stop-and-Wait ARQ konfigurációs paraméterek.

    Attributes
    ----------
    retry_limit:
        Maximális újraküldések száma (az első adáson felül).
        Tehát az összes lehetséges kísérlet: ``retry_limit + 1``.
        Alapértelmezés: 3.
    ack_timeout_us:
        ACK várakozási időablak µs-ban. Ennyi idő után, ha nem érkezik
        ACK, a küldő újraküldi a csomagot. Alapértelmezés: 10 000 µs.
    backoff_base_us:
        Exponenciális backoff alapideje µs-ban. Az i-edik sikertelen
        kísérlet utáni várakozás: ``backoff_base_us * backoff_factor^(i-1)``.
        Alapértelmezés: 5 000 µs.
    backoff_factor:
        Backoff szorzótényező. Alapértelmezés: 2.0 (bináris exp. backoff).
    ack_size_bytes:
        ACK csomag mérete bájtban. Alapértelmezés: 5 B.
    """

    retry_limit: int = 3
    ack_timeout_us: float = 10_000.0
    backoff_base_us: float = 5_000.0
    backoff_factor: float = 2.0
    ack_size_bytes: int = 5


# ---------------------------------------------------------------------------
# ARQResult — egy átvitel eredménye (immutábilis)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ARQResult:
    """Egy ARQ átviteli kísérlet immutábilis eredménye.

    Attributes
    ----------
    success:
        Igaz, ha a csomag sikeresen megérkezett és ACK is érkezett vissza.
    attempts:
        Az elvégzett kísérletek teljes száma (beleértve az elsőt).
    total_tx_us:
        A teljes ARQ-folyamat időigénye µs-ban (adástól az utolsó
        eseményig: sikeres ACK vagy végső backoff).
    energy_j:
        A forrás csomópont energiájának növekménye (delta J) ezen átvitel
        teljes ideje alatt.
    final_pkt:
        A csomag végállapota (Packet referencia; ``delivered`` vagy ``lost``
        mező tükrözi az eredményt).
    """

    success: bool
    attempts: int
    total_tx_us: float
    energy_j: float
    final_pkt: Packet


# ---------------------------------------------------------------------------
# ARQLink — pont-pont összeköttetés Stop-and-Wait ARQ-val
# ---------------------------------------------------------------------------


class ARQLink:
    """Pont-pont összeköttetés Stop-and-Wait ARQ megbízható átvitellel.

    A ``transmit()`` metódus DES scheduler nélkül, idő-lépéses módban
    szimulálja az ARQ-folyamatot:

    1. Az adó regisztrálja az adást a Medium-on.
    2. A ``channel.prr()`` alapján véletlen döntés születik a csomag
       megérkezéséről.
    3. Ha megérkezett: a vevő ACK-ot küld; az adó visszatér sikerrel.
       Ha nem: ``ack_timeout_us`` + exponenciális backoff után újraküldi.
    4. ``retry_limit + 1`` sikertelen kísérlet után ``packet.lost = True``,
       és ``ARQResult(success=False)`` kerül visszaadásra.

    Energia-könyvelés
    -----------------
    * Adáskor: ``energy_src`` TX → IDLE (``tx_duration_us`` hosszán át).
    * Vételkor (dst): RX az adás alatt, majd TX az ACK küldésekor.
    * ACK hallgatásakor (src): RX ``tx_duration_us`` után.
    * Timeout esetén: src RX-ben vár, majd IDLE-re vált.
    * Backoff ideje alatt: src IDLE-ben vár (implicit, flush() kezeli).

    Parameters
    ----------
    src:
        Forrás csomópont azonosítója.
    dst:
        Célállomás csomópont azonosítója.
    channel:
        Rádiós csatornamodell (PRR kiszámításához; a ``distance_m``
        paraméterrel hívódik meg).
    energy_src:
        Forrás csomópont energiamodellje.
    energy_dst:
        Cél csomópont energiamodellje.
    medium:
        Osztott közeg (TX regisztrációhoz és ütközés-detektáláshoz).
    distance_m:
        Az összeköttetés pont-pont távolsága méterben. Alapértelmezés: 10.0 m.
    tx_duration_us:
        Egy adat-csomag adásideje µs-ban. Alapértelmezés: 4 000 µs (4 ms).
    config:
        ARQ konfigurációs paraméterek. Ha None, default ARQConfig() kerül
        felhasználásra.
    rng:
        Determinisztikus véletlenszám-generátor a kézbesítési döntéshez.
        Ha None, seed nélküli generátor jön létre (nem reprodukálható).
    """

    def __init__(
        self,
        src: int,
        dst: int,
        channel: LogDistanceChannel,
        energy_src: EnergyModel,
        energy_dst: EnergyModel,
        medium: Medium,
        distance_m: float = 10.0,
        tx_duration_us: float = 4_000.0,
        config: Optional[ARQConfig] = None,
        rng: Optional[np.random.Generator] = None,
    ) -> None:
        self._src = src
        self._dst = dst
        self._channel = channel
        self._energy_src = energy_src
        self._energy_dst = energy_dst
        self._medium = medium
        self._distance_m = distance_m
        self._tx_duration_us = tx_duration_us
        self._config: ARQConfig = config if config is not None else ARQConfig()
        self._rng: np.random.Generator = (
            rng if rng is not None else np.random.default_rng()
        )

    # ------------------------------------------------------------------
    # Publikus tulajdonságok
    # ------------------------------------------------------------------

    @property
    def src(self) -> int:
        """Forrás csomópont azonosítója."""
        return self._src

    @property
    def dst(self) -> int:
        """Cél csomópont azonosítója."""
        return self._dst

    @property
    def distance_m(self) -> float:
        """A point-to-point összeköttetés távolsága (m)."""
        return self._distance_m

    @property
    def config(self) -> ARQConfig:
        """Aktív ARQ konfiguráció."""
        return self._config

    # ------------------------------------------------------------------
    # Fő átviteli metódus
    # ------------------------------------------------------------------

    def transmit(self, packet: Packet, at_us: float = 0.0) -> ARQResult:
        """Stop-and-Wait ARQ átvitel szimulálása.

        Parameters
        ----------
        packet:
            Az átviendő csomag. A metódus in-place módosítja a csomag
            ``delivered_at`` (siker esetén) vagy ``lost`` (kudarc esetén)
            mezőjét.
        at_us:
            Az átvitel kezdeti szimulált időpontja (µs). Monoton növekvőnek
            kell lennie a csomópont energiamodelljének korábbi időbélyegéhez
            képest.

        Returns
        -------
        ARQResult
            Az átvitel teljes eredménye.
        """
        cfg = self._config
        initial_energy = self._energy_src.consumed_j
        initial_at = at_us
        current_us = at_us

        # ACK adásideje: tx_duration_us-szal arányos, a csomag méretéhez képest skálázva
        ack_dur_us = self._tx_duration_us * cfg.ack_size_bytes / max(packet.size_bytes, 1)

        # Összes lehetséges kísérlet: retry_limit + 1
        total_attempts = cfg.retry_limit + 1

        for attempt in range(1, total_attempts + 1):

            # (a) TX regisztrálása az osztott médiumon
            self._medium.register_tx(
                self._src,
                current_us,
                current_us + self._tx_duration_us,
                packet,
            )

            # Energia: src TX → IDLE
            self._energy_src.transition(EnergyState.TX, current_us)
            self._energy_src.transition(EnergyState.IDLE, current_us + self._tx_duration_us)

            # Energia: dst RX (adást fogad)
            self._energy_dst.transition(EnergyState.RX, current_us)

            # (b) Csatornadöntés: channel.prr() + véletlen szám
            prr_val = self._channel.prr(
                self._distance_m,
                n_bits=packet.size_bits,
                shadowing=True,
            )
            received = bool(self._rng.random() < prr_val)

            if received:
                # (c-siker) Dst ACK küld, src ACK-ot hallgat
                self._energy_dst.transition(
                    EnergyState.TX, current_us + self._tx_duration_us
                )
                self._energy_dst.transition(
                    EnergyState.IDLE,
                    current_us + self._tx_duration_us + ack_dur_us,
                )

                self._energy_src.transition(
                    EnergyState.RX, current_us + self._tx_duration_us
                )
                self._energy_src.transition(
                    EnergyState.IDLE,
                    current_us + self._tx_duration_us + ack_dur_us,
                )

                current_us = current_us + self._tx_duration_us + ack_dur_us
                packet.delivered_at = current_us

                return ARQResult(
                    success=True,
                    attempts=attempt,
                    total_tx_us=current_us - initial_at,
                    energy_j=self._energy_src.consumed_j - initial_energy,
                    final_pkt=packet,
                )

            else:
                # (c-kudarc) Timeout → backoff
                self._energy_dst.transition(
                    EnergyState.IDLE, current_us + self._tx_duration_us
                )

                # Src ACK-ra vár (RX), majd timeout után IDLE
                self._energy_src.transition(
                    EnergyState.RX, current_us + self._tx_duration_us
                )
                self._energy_src.transition(
                    EnergyState.IDLE,
                    current_us + self._tx_duration_us + cfg.ack_timeout_us,
                )

                # Exponenciális backoff: base * factor^(attempt-1)
                backoff_us = cfg.backoff_base_us * (cfg.backoff_factor ** (attempt - 1))
                current_us = (
                    current_us + self._tx_duration_us + cfg.ack_timeout_us + backoff_us
                )

        # Összes kísérlet sikertelen
        packet.lost = True
        # Backoff ideje alatti IDLE fogyasztás integrálása
        self._energy_src.flush(current_us)
        self._energy_dst.flush(current_us)

        return ARQResult(
            success=False,
            attempts=total_attempts,
            total_tx_us=current_us - initial_at,
            energy_j=self._energy_src.consumed_j - initial_energy,
            final_pkt=packet,
        )


# ---------------------------------------------------------------------------
# ARQStats — aggregált statisztika
# ---------------------------------------------------------------------------


@dataclass
class ARQStats:
    """Aggregált statisztika több ARQ átvitelhez.

    Attributes
    ----------
    total_packets:
        Az összes regisztrált átvitel száma (property).

    Metódusok
    ---------
    add(result)         : Egy ARQResult hozzáadása.
    pdr()               : Packet Delivery Ratio (sikeres / összes).
    mean_attempts()     : Átlagos kísérlet-szám.
    mean_energy_j()     : Átlagos energia-felhasználás (J/csomag).

    Example
    -------
    ::

        stats = ARQStats()
        for i in range(100):
            pkt = Packet(packet_id=i, src=0, dst=1)
            stats.add(link.transmit(pkt, at_us=float(i) * 50_000))
        print(f"PDR={stats.pdr():.3f}, mean_hops={stats.mean_attempts():.2f}")
    """

    _results: list[ARQResult] = field(default_factory=list, init=False, repr=False)

    def add(self, result: ARQResult) -> None:
        """Hozzáad egy ARQResult-ot az összesítőhöz."""
        self._results.append(result)

    @property
    def total_packets(self) -> int:
        """Az összes regisztrált átvitel száma."""
        return len(self._results)

    def pdr(self) -> float:
        """Packet Delivery Ratio: sikeresen kézbesített / összes.

        Returns 0.0, ha még nincs egyetlen eredmény sem.
        """
        if not self._results:
            return 0.0
        return sum(1 for r in self._results if r.success) / len(self._results)

    def mean_attempts(self) -> float:
        """Átlagos kísérlet-szám átvitelenként.

        Returns 0.0, ha még nincs egyetlen eredmény sem.
        """
        if not self._results:
            return 0.0
        return sum(r.attempts for r in self._results) / len(self._results)

    def mean_energy_j(self) -> float:
        """Átlagos energia-felhasználás (J) átvitelenként.

        Returns 0.0, ha még nincs egyetlen eredmény sem.
        """
        if not self._results:
            return 0.0
        return sum(r.energy_j for r in self._results) / len(self._results)
