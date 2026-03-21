"""MAC protokoll modellek: Pure ALOHA és CSMA bináris exponenciális backoff-fal.

Ütközés definíciója: két (vagy több) **különböző** csomópont adása időben átfedik
egymást az osztott médiumon.

Osztályok
---------
Medium
    Osztott rádiós közeg; nyilvántartja az adásintervallumokat és retroaktívan
    jelöli az ütköző csomagokat.
TxResult
    Egy MAC-szintű küldési kísérlet eredménye.
ALOHAMac
    Pure ALOHA: azonnali adás, carrier-sense nélkül.
CSMAMac
    CSMA bináris exponenciális backoff-fal (BEB / CSMA/CA).

Példa::

    from wsnsim.models.mac import Medium, ALOHAMac
    from wsnsim.models.packet import Packet

    medium = Medium()
    mac = ALOHAMac(medium=medium, tx_duration_us=4000.0)
    p1 = Packet(packet_id=1, src=1, dst=0)
    p2 = Packet(packet_id=2, src=2, dst=0)
    mac.send(1, p1, at_us=0.0)
    mac.send(2, p2, at_us=0.0)   # egyidejű → ütközés
    assert p1.collided and p2.collided
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.random import Generator

from wsnsim.models.packet import Packet


# ---------------------------------------------------------------------------
# Osztott közeg
# ---------------------------------------------------------------------------


@dataclass
class Medium:
    """Osztott rádiós közeg, ütközés-detektálással.

    Az adásokat ``(start_us, end_us, node_id, packet)`` négyesként tárolja.
    Két adás ütközik, ha időintervallumuk átfed és különböző csomóponthoz
    tartoznak.

    Ha egy új adás ütközik egy már regisztrált adással, a metódus
    **retroaktívan** jelöli az érintett csomag ``lost`` és ``collided``
    mezőjét. Így a hívó az összes küldés elvégzése után is helyesen
    olvashatja ``packet.collided``-t, regisztrálási sorrendre való
    tekintet nélkül.
    """

    _txs: list[tuple[float, float, int | str, Packet | None]] = field(
        default_factory=list, repr=False
    )

    # ------------------------------------------------------------------
    # Publikus interfész
    # ------------------------------------------------------------------

    def register_tx(
        self,
        node_id: int | str,
        start_us: float,
        end_us: float,
        packet: Packet | None = None,
    ) -> bool:
        """Regisztrál egy adásintervallumot.

        Retroaktívan megjelöli az összes korábban regisztrált, ütköző
        csomagot (``lost=True``, ``collided=True``).

        Returns
        -------
        bool
            ``True``, ha az új adás ütközik legalább egy korábbi adással.
        """
        collision = False
        for s, e, nid, pkt in self._txs:
            if nid != node_id and s < end_us and e > start_us:
                collision = True
                if pkt is not None:
                    pkt.lost = True
                    pkt.collided = True
        if collision and packet is not None:
            packet.lost = True
            packet.collided = True
        self._txs.append((start_us, end_us, node_id, packet))
        return collision

    def is_busy_at(
        self, at_us: float, *, exclude_node: int | str | None = None
    ) -> bool:
        """``True``, ha bármely csomópont (kivéve *exclude_node*) éppen adásban van."""
        return any(
            s <= at_us < e and nid != exclude_node
            for s, e, nid, _ in self._txs
        )

    def busy_until(
        self, at_us: float, *, exclude_node: int | str | None = None
    ) -> float:
        """Az első időpont ≥ *at_us*, amikor a csatorna szabad.

        Ha a csatorna már szabad *at_us*-kor, *at_us* értékét adja vissza.
        Egymás mögé szervezett adásokat is figyelembe vesz (iteratív keresés).
        """
        result = at_us
        while True:
            ends = [
                e
                for s, e, nid, _ in self._txs
                if nid != exclude_node and s <= result < e
            ]
            if not ends:
                return result
            result = max(ends)

    def has_collision(self, node_id: int | str) -> bool:
        """``True``, ha *node_id* bármely adása ütközött."""
        my_intervals = [(s, e) for s, e, nid, _ in self._txs if nid == node_id]
        for my_s, my_e in my_intervals:
            for s, e, nid, _ in self._txs:
                if nid != node_id and s < my_e and e > my_s:
                    return True
        return False

    def clear(self) -> None:
        """Törli az összes regisztrált adást."""
        self._txs.clear()

    @property
    def tx_count(self) -> int:
        """Regisztrált adások száma összesen."""
        return len(self._txs)


# ---------------------------------------------------------------------------
# TxResult — küldési kísérlet eredménye
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TxResult:
    """Egy MAC-szintű küldési kísérlet eredménye.

    Attributes
    ----------
    success:          Sikeres kézbesítés (ütközés nélkül).
    collision:        Ütközés történt (legalább az utolsó kísérletben).
    dropped:          Csomag eldobva (max újraküldési kísérlet elérve).
    retries:          Backoff-körök száma.
    backoff_total_us: Az összes backoff várakozási idő (µs).
    tx_start_us:      Az utolsó tényleges adáskezdés időpontja (µs).
    """

    success: bool
    collision: bool
    dropped: bool
    retries: int
    backoff_total_us: float
    tx_start_us: float


# ---------------------------------------------------------------------------
# Pure ALOHA MAC
# ---------------------------------------------------------------------------


@dataclass
class ALOHAMac:
    """Pure ALOHA MAC: azonnali adás, carrier-sense nélkül.

    Két (vagy több) átfedő adás ütközést okoz; mindkét csomag
    ``lost=True``, ``collided=True`` jelölést kap.

    Az *első* küldő nem tud az ütközésről a ``send()`` visszatérési
    értékéből (más csomópont még nem regisztrált), de ``packet.collided``
    az összes ``send()`` hívás után helyes értéket tartalmaz, mivel a
    :class:`Medium` retroaktívan jelöli az érintett csomagokat.

    Parameters
    ----------
    medium:
        Osztott közeg példány.
    tx_duration_us:
        Rögzített adásidő csomagonként (µs). Alap: 4 000 µs
        (32 bájt @ 250 kbps, IEEE 802.15.4).
    rng:
        Véletlen szám generátor (ALOHA-ban nem használt, API konzisztencia).
    """

    medium: Medium
    tx_duration_us: float = 4000.0
    rng: Generator = field(default_factory=lambda: np.random.default_rng(0))

    _tx_count: int = field(default=0, init=False, repr=False)
    _collision_count: int = field(default=0, init=False, repr=False)

    @property
    def tx_count(self) -> int:
        """Összes küldési kísérlet száma."""
        return self._tx_count

    @property
    def collision_count(self) -> int:
        """Azon küldések száma, melyeknél ütközést detektált a hívás pillanatában."""
        return self._collision_count

    def send(
        self, node_id: int | str, packet: Packet, at_us: float
    ) -> TxResult:
        """Azonnali adás *at_us* időpontban.

        A ``TxResult.success`` mező azt tükrözi, ütközött-e a csomag
        a korábban *már* regisztrált adásokkal. Az utólag regisztrált
        ütközéseket a ``packet.collided`` jelző tartalmaz helyesen.
        """
        end_us = at_us + self.tx_duration_us
        collision = self.medium.register_tx(node_id, at_us, end_us, packet)
        self._tx_count += 1
        if collision:
            self._collision_count += 1
        return TxResult(
            success=not collision,
            collision=collision,
            dropped=False,
            retries=0,
            backoff_total_us=0.0,
            tx_start_us=at_us,
        )


# ---------------------------------------------------------------------------
# CSMA MAC bináris exponenciális backoff-fal
# ---------------------------------------------------------------------------


@dataclass
class CSMAMac:
    """CSMA bináris exponenciális backoff-fal (BEB / CSMA/CA).

    Minden adási kísérlet előtt figyeli a csatornát. Ha foglalt, vár,
    amíg szabad nem lesz. Ütközés esetén (rejtett csomópont vagy
    szinte egyidejű érkezés) megduplázza a *contention window*-t egészen
    *cw_max* értékig. *max_retries* sikertelen kísérlet után a csomagot
    elveti.

    Parameters
    ----------
    medium:
        Osztott közeg példány.
    tx_duration_us:
        Rögzített adásidő (µs).
    slot_us:
        Egy backoff slot időtartama (µs). Alap: 1 000 µs (1 ms).
    cw_min:
        Kezdeti contention window mérete (slot). Alap: 8.
    cw_max:
        Maximális contention window mérete (slot). Alap: 256.
    max_retries:
        Maximális backoff-körök száma eldobás előtt. Alap: 7.
    rng:
        Determinisztikus véletlenszám-generátor a backoff-húzásokhoz.
    """

    medium: Medium
    tx_duration_us: float = 4000.0
    slot_us: float = 1000.0
    cw_min: int = 8
    cw_max: int = 256
    max_retries: int = 7
    rng: Generator = field(default_factory=lambda: np.random.default_rng(0))

    _tx_count: int = field(default=0, init=False, repr=False)
    _collision_count: int = field(default=0, init=False, repr=False)
    _drop_count: int = field(default=0, init=False, repr=False)

    @property
    def tx_count(self) -> int:
        """Összes küldési kísérlet száma (minden backoff-kör egy kísérlet)."""
        return self._tx_count

    @property
    def collision_count(self) -> int:
        """Ütköző kísérletek száma."""
        return self._collision_count

    @property
    def drop_count(self) -> int:
        """Eldobott csomagok száma (max_retries elérve)."""
        return self._drop_count

    def send(
        self, node_id: int | str, packet: Packet, at_us: float
    ) -> TxResult:
        """Adás carrier-sense + BEB-del, kezdve *at_us* időponttól.

        A ``TxResult.tx_start_us`` tartalmazza a tényleges adáskezdési
        időpontot, ami *at_us*-nál késői is lehet backoff miatt.
        """
        cw = self.cw_min
        current_us = at_us
        total_backoff_us = 0.0

        for attempt in range(self.max_retries + 1):
            # Carrier sense: várjunk, amíg a csatorna szabad nem lesz
            free_at = self.medium.busy_until(current_us, exclude_node=node_id)
            current_us = max(current_us, free_at)

            # Adási kísérlet
            end_us = current_us + self.tx_duration_us
            collision = self.medium.register_tx(node_id, current_us, end_us, packet)
            self._tx_count += 1

            if not collision:
                # Siker — töröljük az esetleges korábbi kísérlet jelzőit
                packet.lost = False
                packet.collided = False
                return TxResult(
                    success=True,
                    collision=False,
                    dropped=False,
                    retries=attempt,
                    backoff_total_us=total_backoff_us,
                    tx_start_us=current_us,
                )

            # Ütközés → BEB
            self._collision_count += 1
            packet.lost = True
            packet.collided = True

            if attempt < self.max_retries:
                bo_slots = int(self.rng.integers(0, cw))
                bo_us = bo_slots * self.slot_us
                total_backoff_us += bo_us
                current_us += self.tx_duration_us + bo_us
                cw = min(cw * 2, self.cw_max)

        # Max újraküldés elérve → eldobás
        self._drop_count += 1
        return TxResult(
            success=False,
            collision=True,
            dropped=True,
            retries=self.max_retries,
            backoff_total_us=total_backoff_us,
            tx_start_us=current_us,
        )
