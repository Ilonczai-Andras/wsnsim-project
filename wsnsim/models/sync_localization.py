"""Óra-szinkronizáció és RSSI-alapú lokalizáció WSN csomópontokhoz.

Osztályok
---------
ClockDrift
    Egyetlen csomópont kristályóra-eltérésének modellje (ppm alapú).
RSSILocalizer
    RSSI→távolság inverzió és least-squares trilateráció.

Modellezési döntések
--------------------
* A ClockDrift nem szimulálja a fizikai oszcillátort — egyszerű lineáris
  drift-modellt alkalmaz: t_local = t_sim * (1 + ppm * 1e-6) + offset.
* A sync_to() csak az offset_us-t korrigálja; a drift_ppm fizikai adottság,
  nem változtatható szinkronizációval.
* Az RSSILocalizer a csatorna determinisztikus inverz log-distance képletét
  használja (shadowing nélkül); a Monte-Carlo hiba-becslés a konstruktorban
  kapott RNG-t használja.
* A trilateráció linearizált LS megoldása az első anchor-t veszi
  referenciának (nem kerül bele az egyenletrendszerbe).

Példa::

    import numpy as np
    from wsnsim.models.channel import LogDistanceChannel
    from wsnsim.models.sync_localization import ClockDrift, RSSILocalizer

    cd = ClockDrift(drift_ppm=50.0)
    print(cd.clock_error_us(1_000_000.0))   # ≈ 50.0 µs

    ch = LogDistanceChannel(sigma_db=0.0, rng=np.random.default_rng(0))
    loc = RSSILocalizer(channel=ch, rng=np.random.default_rng(42))
    anchors = [(0.0, 0.0), (50.0, 0.0), (0.0, 50.0)]
    rssi_vals = [ch.rssi_dbm(35.36), ch.rssi_dbm(35.36), ch.rssi_dbm(35.36)]
    x_est, y_est = loc.estimate(anchors, rssi_vals)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from wsnsim.models.channel import LogDistanceChannel


# ---------------------------------------------------------------------------
# ClockDrift — kristályóra eltérés modellje
# ---------------------------------------------------------------------------


@dataclass
class ClockDrift:
    """Lineáris drift-modell egy WSN csomópont kristályórájához.

    Attributes
    ----------
    drift_ppm:
        Óra eltérése parts-per-million egységben. Tipikus tartomány:
        ±20–100 ppm. Pozitív → gyorsabban jár; negatív → lassabban.
    offset_us:
        Szinkronizáció által beállított korrekció [µs]. Alapértelmezés: 0.0.
        A ``sync_to()`` metódus módosítja ezt az értéket.

    Example
    -------
    ::

        cd = ClockDrift(drift_ppm=50.0)
        cd.clock_error_us(1_000_000.0)   # → 50.0 µs
        cd.sync_to(1_000_000.0)
        cd.clock_error_us(1_000_000.0)   # → 0.0 µs
    """

    drift_ppm: float
    offset_us: float = 0.0

    # ------------------------------------------------------------------
    # Publikus metódusok
    # ------------------------------------------------------------------

    def local_time(self, sim_time_us: float) -> float:
        """A csomópont lokális óraállása az ideális szimulációs idő alapján.

        Képlet: ``t_local = sim_time_us * (1 + drift_ppm * 1e-6) + offset_us``

        Parameters
        ----------
        sim_time_us:
            Ideális szimulációs idő [µs].

        Returns
        -------
        float
            Lokális óraállás [µs].
        """
        return sim_time_us * (1.0 + self.drift_ppm * 1e-6) + self.offset_us

    def clock_error_us(self, sim_time_us: float) -> float:
        """Eltérés az ideális szimulációs időtől.

        Képlet: ``local_time(sim_time_us) - sim_time_us``

        Parameters
        ----------
        sim_time_us:
            Ideális szimulációs idő [µs].

        Returns
        -------
        float
            Órahibá [µs]. Pozitív → siet; negatív → késik.
        """
        return self.local_time(sim_time_us) - sim_time_us

    def sync_to(self, sim_time_us: float) -> None:
        """Szinkronizáció: beállítja az ``offset_us``-t úgy, hogy
        ``local_time(sim_time_us) == sim_time_us`` teljesüljön.

        Képlet: ``offset_us = -sim_time_us * drift_ppm * 1e-6``

        A ``drift_ppm`` fizikai adottság — ezt nem módosítja. A
        szinkronizáció után az óra ismét elkezd eltérni a drift miatt.

        Parameters
        ----------
        sim_time_us:
            A szinkronizáció szimulált időpontja [µs].
        """
        self.offset_us = -sim_time_us * self.drift_ppm * 1e-6


# ---------------------------------------------------------------------------
# RSSILocalizer — RSSI→távolság és least-squares trilateráció
# ---------------------------------------------------------------------------


class RSSILocalizer:
    """RSSI-alapú távolságbecslés és least-squares trilateráció.

    Az inverz log-distance modell a csatorna paraméterei alapján becsüli
    a távolságot az RSSI értékből (shadowing nélküli, determinisztikus
    inverz). A ``localization_error()`` Monte-Carlo módszerrel becsüli
    az RSSI-zaj hatását a lokalizációs hibára.

    Parameters
    ----------
    channel:
        Konfigurált ``LogDistanceChannel`` példány. Felhasznált mezők:
        ``rssi_dbm()``, ``d0_m``, ``n``, ``tx_power_dbm``.
    rng:
        NumPy véletlenszám-generátor a Monte-Carlo szimulációhoz.
        A konstruktorban kapott referencia — nem jön létre új generátor.
    """

    def __init__(
        self,
        channel: LogDistanceChannel,
        rng: np.random.Generator,
    ) -> None:
        self._ch = channel
        self._rng = rng

    # ------------------------------------------------------------------
    # RSSI → távolság
    # ------------------------------------------------------------------

    def rssi_to_distance(self, rssi_dbm: float) -> float:
        """RSSI értékből becsüli a távolságot [m].

        Inverz log-distance képlet (shadowing nélkül):

        .. math::

            d = d_0 \\cdot 10^{\\frac{P_{tx} - RSSI}{10 \\cdot n}}

        Klippelés: ``[d0_m, 200.0]`` m.

        Parameters
        ----------
        rssi_dbm:
            Vett jelerősség [dBm].

        Returns
        -------
        float
            Becsült távolság [m], klippelve [d0_m, 200.0].
        """
        ch = self._ch
        exponent = (ch.tx_power_dbm - rssi_dbm - ch.pl0_db) / (10.0 * ch.n)
        d_est = ch.d0_m * (10.0 ** exponent)
        return float(max(ch.d0_m, min(d_est, 200.0)))

    # ------------------------------------------------------------------
    # Least-squares trilateráció
    # ------------------------------------------------------------------

    def estimate(
        self,
        anchors: list[tuple[float, float]],
        rssi_values: list[float],
    ) -> tuple[float, float]:
        """Least-squares trilateráció RSSI alapján.

        Az első anchor referenciaként szerepel; a linearizált
        egyenletrendszer az összes többi anchor-anchor párra épül.

        .. math::

            A \\mathbf{x} = \\mathbf{b}

        ahol:

        .. math::

            A_i = [2(x_i - x_0),\\; 2(y_i - y_0)]

            b_i = d_0^2 - d_i^2 + x_i^2 - x_0^2 + y_i^2 - y_0^2

        Parameters
        ----------
        anchors:
            Anchor pozíciók listája: ``[(x0,y0), (x1,y1), ...]``.
            Legalább 3 anchor szükséges.
        rssi_values:
            Mért RSSI értékek [dBm] minden anchornál (ugyanolyan sorrendben).

        Returns
        -------
        tuple[float, float]
            Becsült `(x_est, y_est)` pozíció [m].

        Raises
        ------
        ValueError
            Ha kevesebb mint 3 anchor van.
        """
        if len(anchors) < 3:
            raise ValueError(
                f"Legalább 3 anchor szükséges a trilaterációhoz, "
                f"kapott: {len(anchors)}"
            )

        # Távolságbecslések minden anchorra
        distances = [self.rssi_to_distance(r) for r in rssi_values]

        x0, y0 = anchors[0]
        d0 = distances[0]

        # Linearizált egyenletrendszer (i = 1 .. N-1)
        rows_A = []
        rows_b = []
        for i in range(1, len(anchors)):
            xi, yi = anchors[i]
            di = distances[i]
            rows_A.append([2.0 * (xi - x0), 2.0 * (yi - y0)])
            rows_b.append(
                d0 ** 2 - di ** 2 + xi ** 2 - x0 ** 2 + yi ** 2 - y0 ** 2
            )

        A = np.array(rows_A, dtype=float)
        b = np.array(rows_b, dtype=float)
        result, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
        return float(result[0]), float(result[1])

    # ------------------------------------------------------------------
    # Monte-Carlo lokalizációs hiba
    # ------------------------------------------------------------------

    def localization_error(
        self,
        anchors: list[tuple[float, float]],
        true_pos: tuple[float, float],
        noise_sigma_db: float = 0.0,
        n_trials: int = 200,
    ) -> float:
        """Monte-Carlo lokalizációs hiba [m] adott RSSI-zaj mellett.

        Minden triálban:
        1. Valódi RSSI kiszámítása minden anchorra: ``channel.rssi_dbm(dist)``.
        2. Gauss-zaj hozzáadása: ``rssi + rng.normal(0, noise_sigma_db)``.
        3. ``estimate()`` meghívása, euklideszi hiba kiszámítása.

        Parameters
        ----------
        anchors:
            Anchor pozíciók listája.
        true_pos:
            Ismeretlen csomópont valódi pozíciója ``(x, y)`` [m].
        noise_sigma_db:
            RSSI mérési zaj szórása [dB]. 0.0 = zaj nélküli, determinisztikus.
        n_trials:
            Monte-Carlo iterációk száma. Alapértelmezés: 200.

        Returns
        -------
        float
            Átlagos euklideszi lokalizációs hiba [m].
        """
        tx, ty = true_pos
        true_rssi = [
            self._ch.rssi_dbm(math.sqrt((ax - tx) ** 2 + (ay - ty) ** 2))
            for ax, ay in anchors
        ]

        errors = []
        for _ in range(n_trials):
            if noise_sigma_db > 0.0:
                noisy = [
                    r + float(self._rng.normal(0.0, noise_sigma_db))
                    for r in true_rssi
                ]
            else:
                noisy = list(true_rssi)

            x_est, y_est = self.estimate(anchors, noisy)
            err = math.sqrt((x_est - tx) ** 2 + (y_est - ty) ** 2)
            errors.append(err)

        return float(np.mean(errors))
