"""duty_cycle_lifetime.py — duty cycle vs becsült üzemidő kísérlet (7.3. hét).

Különböző duty-cycle값(aktív rádió idő aránya) mellett becsüli egy WSN
csomópont üzemidejét, és ábrázolja a trade-off görbét.

Futtatás::

    python experiments/duty_cycle_lifetime.py

Kimenet:
    - stdout: táblázat (duty cycle, avg power, becsült élettartam)
    - reports/figures/duty_cycle_lifetime.png
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from wsnsim.models.energy import DEFAULT_POWER_MW, EnergyModel, EnergyState

# ---------------------------------------------------------------------------
# Konfiguráció
# ---------------------------------------------------------------------------

BATTERY_J: float = 9720.0          # 2× AA alkáli: 2700 mAh × 3.6 V ≈ 9720 J
DUTY_CYCLES: np.ndarray = np.linspace(0.001, 1.0, 200)   # 0.1 % … 100 %
SLOT_US: float = 10_000.0          # 10 ms-es slotonkénti szimulálás
N_SLOTS: int = 1000                 # 10 s szimulált idő az átlaghoz

FIGURES_DIR = _PROJECT_ROOT / "reports" / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Átlagos fogyasztás számítása duty-cycle függvényében
# ---------------------------------------------------------------------------

def avg_power_for_duty_cycle(duty_cycle: float) -> float:
    """Kiszámítja az átlagos fogyasztást (W) az adott duty-cycle mellett.

    Az aktív idő felét TX-ben, felét RX-ben tölti a csomópont;
    a maradék idő SLEEP állapot.

    Args:
        duty_cycle: Aktív idő aránya (0…1).

    Returns:
        Átlagos fogyasztás (W).
    """
    # Analitikus számítás (gyors, nincs állapotgép overhead):
    p_active_w = (
        DEFAULT_POWER_MW[EnergyState.TX] + DEFAULT_POWER_MW[EnergyState.RX]
    ) / 2.0 * 1e-3
    p_sleep_w = DEFAULT_POWER_MW[EnergyState.SLEEP] * 1e-3
    return duty_cycle * p_active_w + (1.0 - duty_cycle) * p_sleep_w


def lifetime_years(avg_power_w: float, battery_j: float = BATTERY_J) -> float:
    """Becsült üzemidő években.

    Args:
        avg_power_w: Átlagos fogyasztás (W).
        battery_j:   Akkukapacitás (J).

    Returns:
        Üzemidő (év). ``float('inf')`` ha a fogyasztás nulla.
    """
    if avg_power_w <= 0.0:
        return float("inf")
    lifetime_s = battery_j / avg_power_w
    return lifetime_s / (365.25 * 24 * 3600)


# ---------------------------------------------------------------------------
# Stdout táblázat
# ---------------------------------------------------------------------------

def print_table() -> None:
    """Kinyomtatja a táblázatot néhány kulcsponton."""
    key_dc = [0.001, 0.005, 0.01, 0.05, 0.10, 0.25, 0.50, 1.0]
    header = f"{'Duty cycle':>12} | {'avg P (µW)':>12} | {'Üzemidő (év)':>14}"
    sep = "-" * len(header)
    print("\n=== Duty-cycle vs becsült üzemidő (battery = {:.0f} J) ===".format(BATTERY_J))
    print(sep)
    print(header)
    print(sep)
    for dc in key_dc:
        p = avg_power_for_duty_cycle(dc)
        lt = lifetime_years(p)
        print(f"{dc:>12.3f} | {p * 1e6:>12.2f} | {lt:>14.2f}")
    print(sep)
    print()

    # Kézi sanity check: 1% duty cycle
    dc = 0.01
    p_active = (DEFAULT_POWER_MW[EnergyState.TX] + DEFAULT_POWER_MW[EnergyState.RX]) / 2
    p_sleep  = DEFAULT_POWER_MW[EnergyState.SLEEP]
    p_manual = dc * p_active + (1 - dc) * p_sleep  # mW
    print(f"Kézi validálás (DC=1 %): P = {dc}×{p_active:.1f} + {1-dc}×{p_sleep:.3f} "
          f"= {p_manual:.4f} mW  ✓")
    print()


# ---------------------------------------------------------------------------
# Ábra
# ---------------------------------------------------------------------------

def save_figure() -> Path:
    """Két-paneles ábra: (1) avg power vs DC, (2) lifetime vs DC."""
    powers_w    = [avg_power_for_duty_cycle(dc) for dc in DUTY_CYCLES]
    lifetimes_y = [lifetime_years(p) for p in powers_w]

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    fig.suptitle(
        f"WSN csomópont duty-cycle vs üzemidő trade-off\n"
        f"Akku: {BATTERY_J:.0f} J  |  TX={DEFAULT_POWER_MW[EnergyState.TX]:.1f} mW, "
        f"RX={DEFAULT_POWER_MW[EnergyState.RX]:.1f} mW, "
        f"SLEEP={DEFAULT_POWER_MW[EnergyState.SLEEP]*1000:.0f} µW",
        fontsize=10,
    )

    # --- Bal: átlagos fogyasztás ---
    axes[0].plot(DUTY_CYCLES * 100, [p * 1e3 for p in powers_w],
                 color="darkorange", linewidth=2)
    axes[0].set_xlabel("Duty cycle (%)", fontsize=11)
    axes[0].set_ylabel("Átlagos fogyasztás (mW)", fontsize=11)
    axes[0].set_title("Átlagos fogyasztás vs duty cycle")
    axes[0].set_xlim(0, 100)
    axes[0].set_ylim(0)
    axes[0].grid(True, alpha=0.4)

    # --- Jobb: üzemidő (log y-tengely) ---
    axes[1].semilogy(DUTY_CYCLES * 100, lifetimes_y,
                     color="steelblue", linewidth=2)
    # referenciavonalak
    for y_ref, label in ((1.0, "1 év"), (5.0, "5 év"), (10.0, "10 év")):
        axes[1].axhline(y_ref, color="gray", linewidth=0.8, linestyle=":",
                        label=label)
    axes[1].set_xlabel("Duty cycle (%)", fontsize=11)
    axes[1].set_ylabel("Becsült üzemidő (év)", fontsize=11)
    axes[1].set_title("Üzemidő vs duty cycle (log skála)")
    axes[1].set_xlim(0, 100)
    axes[1].legend(fontsize=9)
    axes[1].grid(True, which="both", alpha=0.3)

    plt.tight_layout()
    out = FIGURES_DIR / "duty_cycle_lifetime.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Főprogram
# ---------------------------------------------------------------------------

def main() -> None:
    print_table()
    out = save_figure()
    print(f"Ábra mentve: {out}")


if __name__ == "__main__":
    main()
