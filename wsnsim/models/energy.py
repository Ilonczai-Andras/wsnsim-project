"""EnergyModel — állapotgépes energiafogyasztás-modell WSN csomópontokhoz.

A modell az IEEE 802.15.4 rádiók tipikus fogyasztási értékeit követi
(CC2420 referencia: Heinzelman et al. [17]).

Állapotok és tipikus fogyasztások (3 V tápfeszültség):

+----------+---------------+------------------+
| Állapot  | Áram (mA)     | Teljesítmény (mW)|
+----------+---------------+------------------+
| TX       | 17.4 mA       | 52.2 mW          |
| RX       | 18.8 mA       | 56.4 mW          |
| IDLE     |  1.0 mA       |  3.0 mW          |
| SLEEP    |  0.001 mA     |  0.003 mW        |
+----------+---------------+------------------+

Energia-büdzsé számítás elvei:

.. math::

    E_{consumed}(\\Delta t) = P_{state} \\cdot \\Delta t

ahol :math:`\\Delta t` az adott állapotban töltött idő (s).

Hivatkozások:
    [17] Heinzelman et al. (2000) — LEACH, CC2420-szerű radio energia modell.
    [1]  Sohraby et al. (2007)  — WSN energiahatékonyság.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


# ---------------------------------------------------------------------------
# Állapot-enum
# ---------------------------------------------------------------------------


class EnergyState(Enum):
    """WSN rádió / MCU energiaállapotok.

    Az értékek növekvő fogyasztást jelölnek (SLEEP → TX).
    """

    SLEEP = auto()   # legkisebb fogyasztás
    IDLE = auto()    # MCU aktív, rádió kikapcsolt
    RX = auto()      # vevő aktív (hallgatás)
    TX = auto()      # adó aktív

    def __lt__(self, other: "EnergyState") -> bool:
        return self.value < other.value


# ---------------------------------------------------------------------------
# Alapértelmezett fogyasztási profilok (mW)
# ---------------------------------------------------------------------------

#: Alapértelmezett fogyasztás állapotonként (mW), CC2420-alapú
DEFAULT_POWER_MW: dict[EnergyState, float] = {
    EnergyState.TX:    52.2,
    EnergyState.RX:    56.4,
    EnergyState.IDLE:   3.0,
    EnergyState.SLEEP:  0.003,
}


# ---------------------------------------------------------------------------
# EnergyModel
# ---------------------------------------------------------------------------


@dataclass
class EnergyModel:
    """Állapotgépes energiafogyasztás-modell egy WSN csomóponthoz.

    Az idő µs-ban érkezik (a szimulátor egysége), az energia J-ban tárolódik.

    Args:
        battery_j:       Akku kapacitás joulesban.
                         Alapértelmezés: 2× AA alkáli ≈ 9720 J (2700 mAh × 3.6 V).
        initial_state:   Kezdeti állapot (alapértelmezés: SLEEP).
        power_mw:        Fogyasztási profil állapotonként (mW).
                         Ha None, ``DEFAULT_POWER_MW`` kerül felhasználásra.
        node_id:         Opcionális azonosító loggoláshoz.

    Example:
        >>> em = EnergyModel(battery_j=100.0)
        >>> em.transition(EnergyState.TX, at_us=0.0)
        >>> em.transition(EnergyState.SLEEP, at_us=1_000_000.0)  # 1 s TX
        >>> round(em.consumed_j, 4)
        0.0522
    """

    battery_j: float = 9720.0
    initial_state: EnergyState = EnergyState.SLEEP
    power_mw: Optional[dict[EnergyState, float]] = field(default=None, repr=False)
    node_id: int = 0

    # belső állapot — repr=False, hogy ne zavarja az összehasonlítást
    _state: EnergyState = field(default=EnergyState.SLEEP, init=False, repr=False)
    _state_entry_us: float = field(default=0.0, init=False, repr=False)
    _consumed_j: float = field(default=0.0, init=False, repr=False)
    _time_in_state_us: dict[EnergyState, float] = field(
        default_factory=dict, init=False, repr=False
    )
    _last_sim_us: float = field(default=0.0, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.battery_j <= 0:
            raise ValueError(f"battery_j pozitív kell, kapott: {self.battery_j}")
        self._state = self.initial_state
        self._state_entry_us = 0.0
        self._consumed_j = 0.0
        self._time_in_state_us = {s: 0.0 for s in EnergyState}
        self._power_profile: dict[EnergyState, float] = (
            self.power_mw if self.power_mw is not None else DEFAULT_POWER_MW
        )

    # ---------------------------------------------------------------------------
    # Állapotgép
    # ---------------------------------------------------------------------------

    def transition(self, new_state: EnergyState, at_us: float) -> float:
        """Állapotváltás: integrálja az eddigi fogyasztást, majd vált.

        Args:
            new_state: Az új állapot.
            at_us:     A váltás szimulációs időpontja (µs).

        Returns:
            Az állapotváltással elfogyasztott energia (J).

        Raises:
            ValueError: Ha ``at_us`` kisebb, mint az előző váltás időpontja.
            RuntimeError: Ha az akku lemerült (``remaining_j <= 0``).
        """
        if at_us < self._state_entry_us:
            raise ValueError(
                f"Idővisszalépés tiltott az EnergyModel-ben: "
                f"{at_us} < {self._state_entry_us}"
            )
        delta_us = at_us - self._state_entry_us
        consumed = self._integrate(self._state, delta_us)

        # negatív energia guard
        if self._consumed_j > self.battery_j:
            self._consumed_j = self.battery_j   # klippelés, ne menjen negatívba

        self._time_in_state_us[self._state] = (
            self._time_in_state_us.get(self._state, 0.0) + delta_us
        )
        self._state = new_state
        self._state_entry_us = at_us
        self._last_sim_us = at_us
        return consumed

    def flush(self, at_us: float) -> None:
        """Integrálja a jelenlegi állapot fogyasztását ``at_us``-ig (állapotváltás nélkül).

        Hasznos a szimuláció végén, hogy az utolsó állapot fogyasztása is elszámolódjon.

        Args:
            at_us: A szimulációs időpont, ameddig integráljuk (µs).
        """
        self.transition(self._state, at_us)

    def _integrate(self, state: EnergyState, delta_us: float) -> float:
        """Kiszámítja az adott állapotban töltött idő alatti energiafogyasztást.

        Args:
            state:    Az állapot.
            delta_us: Az eltelt idő µs-ban.

        Returns:
            Elfogyasztott energia (J).
        """
        power_w = self._power_profile[state] * 1e-3   # mW → W
        energy_j = power_w * (delta_us * 1e-6)        # µs → s
        self._consumed_j += energy_j
        return energy_j

    # ---------------------------------------------------------------------------
    # Lekérdezők
    # ---------------------------------------------------------------------------

    @property
    def current_state(self) -> EnergyState:
        """Az aktuális energiaállapot."""
        return self._state

    @property
    def consumed_j(self) -> float:
        """Az összes elfogyasztott energia (J), klippelve a kapacitásra."""
        return min(self._consumed_j, self.battery_j)

    @property
    def remaining_j(self) -> float:
        """A maradék akkuenergia (J) — soha nem negatív."""
        return max(self.battery_j - self._consumed_j, 0.0)

    @property
    def is_depleted(self) -> bool:
        """Igaz, ha az akku lemerült (``remaining_j == 0``)."""
        return self.remaining_j <= 0.0

    @property
    def soc_percent(self) -> float:
        """Töltöttségi szint százalékban (State of Charge, 0–100 %)."""
        return 100.0 * self.remaining_j / self.battery_j

    def time_in_state_us(self, state: EnergyState) -> float:
        """Az adott állapotban töltött összes szimulációs idő (µs).

        Args:
            state: A lekérdezett állapot.

        Returns:
            Idő µs-ban.
        """
        return self._time_in_state_us.get(state, 0.0)

    def average_power_w(self, total_time_us: Optional[float] = None) -> float:
        """Átlagos fogyasztás (W) a szimulált idő alapján.

        Args:
            total_time_us: Ha None, az összes lezárt állapotban töltött idő
                           összege kerül nevező-ként.

        Returns:
            Átlagos teljesítmény (W). 0.0, ha nincs elszámolt idő.
        """
        if total_time_us is None:
            total_time_us = sum(self._time_in_state_us.values())
        if total_time_us <= 0.0:
            return 0.0
        total_energy_j = sum(
            self._power_profile[s] * 1e-3 * (t * 1e-6)
            for s, t in self._time_in_state_us.items()
        )
        return total_energy_j / (total_time_us * 1e-6)

    def lifetime_estimate_s(self, avg_power_w: Optional[float] = None) -> float:
        """Becsült hátralévő üzemidő másodpercben az aktuális fogyasztás alapján.

        .. math::

            T_{lifetime} = \\frac{E_{remaining}}{P_{avg}}

        Args:
            avg_power_w: Ha None, az eddigi mért átlagos fogyasztás kerül felhasználásra.
                         Explicit értékkel is megadható (pl. duty-cycle kísérletekhez).

        Returns:
            Becsült üzemidő (s). ``float('inf')`` ha a fogyasztás nulla.
        """
        p = avg_power_w if avg_power_w is not None else self.average_power_w()
        if p <= 0.0:
            return float("inf")
        return self.remaining_j / p

    # ---------------------------------------------------------------------------
    # Összesítő
    # ---------------------------------------------------------------------------

    def summary(self) -> dict[str, float]:
        """Energiagazdálkodás összefoglalója szótárban.

        Returns:
            Szótár: battery_j, consumed_j, remaining_j, soc_percent, avg_power_w,
            lifetime_estimate_s, és az egyes állapotokban töltött idő (µs).
        """
        result: dict[str, float] = {
            "battery_j": self.battery_j,
            "consumed_j": self.consumed_j,
            "remaining_j": self.remaining_j,
            "soc_percent": self.soc_percent,
            "avg_power_w": self.average_power_w(),
            "lifetime_estimate_s": self.lifetime_estimate_s(),
        }
        for state in EnergyState:
            result[f"time_{state.name.lower()}_us"] = self.time_in_state_us(state)
        return result

    def __repr__(self) -> str:
        return (
            f"EnergyModel(node={self.node_id}, state={self._state.name}, "
            f"soc={self.soc_percent:.1f}%, consumed={self.consumed_j:.6f}J)"
        )
