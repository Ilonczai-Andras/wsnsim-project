"""prr_curve.py — PRR(d) görbék kísérlet (7.2. hét).

Több shadowing szórás (sigma) értékre ábrázolja a vett csomag-arány (PRR)
függvényét a távolság (d) függvényében.

Futtatás::

    python experiments/prr_curve.py

Kimenet:
    - stdout: link budget táblázat 2 mintapontra (kézi validálás)
    - reports/figures/prr_curve.png
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

from wsnsim.models.channel import LogDistanceChannel

# ---------------------------------------------------------------------------
# Konfiguráció
# ---------------------------------------------------------------------------

SEED: int = 42
DISTANCES_M = np.linspace(1.0, 120.0, 200)   # 1 m … 120 m
N_BITS: int = 256                              # 32 bájt csomag
N_MONTE_CARLO: int = 500                       # átlagoláshoz
SIGMAS_DB: list[float] = [0.0, 3.0, 6.0]      # shadowing szórások (dB)

CHANNEL_PARAMS = dict(
    n=2.7,
    pl0_db=55.0,
    d0_m=1.0,
    tx_power_dbm=0.0,
    noise_floor_dbm=-95.0,
)

FIGURES_DIR = _PROJECT_ROOT / "reports" / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Kézi validálás (stdout)
# ---------------------------------------------------------------------------

def print_link_budget_table() -> None:
    """Kiírja a link budget összefoglalóját 2 mintapontra (d=10 m, d=50 m)."""
    ch = LogDistanceChannel(**CHANNEL_PARAMS, sigma_db=0.0,
                            rng=np.random.default_rng(SEED))
    print("\n=== Link Budget — kézi validálás (σ=0 dB) ===")
    header = (
        f"{'d (m)':>7} | {'PL (dB)':>9} | {'RSSI (dBm)':>11} | "
        f"{'SNR (dB)':>9} | {'BER':>10} | {'PRR':>7}"
    )
    print(header)
    print("-" * len(header))
    for d in (10.0, 50.0):
        lb = ch.link_budget(d)
        print(
            f"{lb['d_m']:>7.1f} | {lb['path_loss_db']:>9.2f} | "
            f"{lb['rssi_dbm']:>11.2f} | {lb['snr_db']:>9.2f} | "
            f"{lb['ber']:>10.2e} | {lb['prr_256bit']:>7.4f}"
        )
    print()
    print("Kézi ellenőrzés:")
    import math
    for d, label in ((10.0, "10 m"), (50.0, "50 m")):
        pl_manual = 55.0 + 10 * 2.7 * math.log10(d / 1.0)
        print(f"  PL({label}) = 55 + 10×2.7×log10({d}) = {pl_manual:.2f} dB  ✓")
    print()


# ---------------------------------------------------------------------------
# PRR görbék számítása
# ---------------------------------------------------------------------------

def compute_prr_curves() -> dict[float, list[float]]:
    """PRR(d) görbéket számít minden sigma értékre.

    Shadowingos esetben Monte-Carlo átlagolást végez N_MONTE_CARLO mintával.

    Returns:
        Szótár: sigma → PRR-lista (indexei DISTANCES_M-nek felelnek meg).
    """
    curves: dict[float, list[float]] = {}
    for sigma in SIGMAS_DB:
        rng = np.random.default_rng(SEED)
        ch = LogDistanceChannel(**CHANNEL_PARAMS, sigma_db=sigma, rng=rng)
        if sigma == 0.0:
            prr_list = [ch.prr(float(d), n_bits=N_BITS, shadowing=False)
                        for d in DISTANCES_M]
        else:
            prr_list = [ch.prr_mean(float(d), n_bits=N_BITS,
                                     n_samples=N_MONTE_CARLO)
                        for d in DISTANCES_M]
        curves[sigma] = prr_list
        print(f"  σ={sigma:.0f} dB kész")
    return curves


# ---------------------------------------------------------------------------
# Ábra generálás
# ---------------------------------------------------------------------------

def save_figure(curves: dict[float, list[float]]) -> Path:
    """PRR(d) görbéket rajzol és ment PNG-be.

    Args:
        curves: compute_prr_curves() visszatérési értéke.

    Returns:
        A mentett fájl elérési útja.
    """
    fig, ax = plt.subplots(figsize=(8, 5))

    styles = {0.0: "-", 3.0: "--", 6.0: "-."}
    colors = {0.0: "steelblue", 3.0: "darkorange", 6.0: "forestgreen"}

    for sigma, prr_list in sorted(curves.items()):
        label = f"σ = {sigma:.0f} dB" + (" (determinisztikus)" if sigma == 0.0 else " (MC átlag)")
        ax.plot(
            DISTANCES_M,
            prr_list,
            linestyle=styles.get(sigma, "-"),
            color=colors.get(sigma, "black"),
            linewidth=2,
            label=label,
        )

    # Vízszintes referenciavonalak
    for ythr, color in ((0.9, "gray"), (0.5, "lightgray")):
        ax.axhline(ythr, color=color, linewidth=0.8, linestyle=":")

    ax.set_xlabel("Távolság, d (m)", fontsize=12)
    ax.set_ylabel("Csomag-vételi arány, PRR", fontsize=12)
    ax.set_title(
        f"PRR(d) — Log-distance + log-normal shadowing\n"
        f"n={CHANNEL_PARAMS['n']}, PL₀={CHANNEL_PARAMS['pl0_db']} dB, "
        f"d₀={CHANNEL_PARAMS['d0_m']} m, "
        f"Ptx={CHANNEL_PARAMS['tx_power_dbm']} dBm, "
        f"Nnoise={CHANNEL_PARAMS['noise_floor_dbm']} dBm, "
        f"L={N_BITS} bit",
        fontsize=10,
    )
    ax.set_xlim(DISTANCES_M[0], DISTANCES_M[-1])
    ax.set_ylim(-0.02, 1.05)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1.0))
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.4)

    plt.tight_layout()
    out_path = FIGURES_DIR / "prr_curve.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


# ---------------------------------------------------------------------------
# Főprogram
# ---------------------------------------------------------------------------

def main() -> None:
    print_link_budget_table()
    print("PRR görbék számítása...")
    curves = compute_prr_curves()
    out = save_figure(curves)
    print(f"Ábra mentve: {out}")


if __name__ == "__main__":
    main()
