"""7.8. hét — Lokalizációs hiba vs RSSI-zaj sweep.

Paraméterek:
  SEED           = 42
  N_TRIALS       = 300          # Monte-Carlo iterációk száma
  NOISE_SIGMAS_DB = [0,1,2,3,4,6,8,10]  dB
  TRUE_POS       = (25.0, 25.0) m
  ANCHORS        = 4 sarokpont 50×50 m-es területen

Kimenet:
  - Stdout táblázat: noise_sigma_db | mean_error_m | min_error_m | max_error_m
  - reports/figures/localization_error.png

Reprodukálhatóság: seed=42, kétszeri futtatás azonos táblázatot ad.
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from wsnsim.models.channel import LogDistanceChannel
from wsnsim.models.sync_localization import RSSILocalizer

# ---------------------------------------------------------------------------
# Konstansok
# ---------------------------------------------------------------------------

SEED: int = 42
N_TRIALS: int = 300
NOISE_SIGMAS_DB: list[float] = [0, 1, 2, 3, 4, 6, 8, 10]
TRUE_POS: tuple[float, float] = (25.0, 25.0)
ANCHORS: list[tuple[float, float]] = [
    (0.0,  0.0),
    (50.0, 0.0),
    (0.0,  50.0),
    (50.0, 50.0),
]

# ---------------------------------------------------------------------------
# Csatorna (sigma_db=0: a zajt explicit adjuk hozzá a kísérletben)
# ---------------------------------------------------------------------------

channel = LogDistanceChannel(
    n=2.7,
    d0_m=1.0,
    pl0_db=55.0,
    tx_power_dbm=0.0,
    noise_floor_dbm=-100.0,
    sigma_db=0.0,
    rng=np.random.default_rng(SEED),
)

# ---------------------------------------------------------------------------
# Sweep
# ---------------------------------------------------------------------------

records: list[dict] = []

for sigma in NOISE_SIGMAS_DB:
    # Minden sigma-értékhez azonos seed → reprodukálható
    localizer = RSSILocalizer(
        channel=channel,
        rng=np.random.default_rng(SEED),
    )

    # Egyedi trial-hibák gyűjtése a min/max számításhoz
    tx, ty = TRUE_POS
    true_rssi = [
        channel.rssi_dbm(math.sqrt((ax - tx) ** 2 + (ay - ty) ** 2))
        for ax, ay in ANCHORS
    ]

    trial_errors: list[float] = []
    rng = np.random.default_rng(SEED)
    for _ in range(N_TRIALS):
        if sigma > 0.0:
            noisy = [r + float(rng.normal(0.0, sigma)) for r in true_rssi]
        else:
            noisy = list(true_rssi)
        x_est, y_est = localizer.estimate(ANCHORS, noisy)
        trial_errors.append(math.sqrt((x_est - tx) ** 2 + (y_est - ty) ** 2))

    records.append({
        "sigma": sigma,
        "mean": float(np.mean(trial_errors)),
        "min":  float(np.min(trial_errors)),
        "max":  float(np.max(trial_errors)),
    })

# ---------------------------------------------------------------------------
# Stdout táblázat
# ---------------------------------------------------------------------------

header = f"{'noise_sigma_db':>14} | {'mean_error_m':>12} | {'min_error_m':>11} | {'max_error_m':>11}"
sep = "-" * len(header)
print("\n=== Lokalizációs hiba vs RSSI-zaj ===")
print(header)
print(sep)
for row in records:
    print(
        f"{row['sigma']:>14.1f} | {row['mean']:>12.4f} | "
        f"{row['min']:>11.4f} | {row['max']:>11.4f}"
    )

# ---------------------------------------------------------------------------
# Ábra
# ---------------------------------------------------------------------------

sigmas = [r["sigma"] for r in records]
means  = [r["mean"]  for r in records]
mins   = [r["min"]   for r in records]
maxs   = [r["max"]   for r in records]

fig, ax = plt.subplots(figsize=(8, 5))

ax.plot(sigmas, means, "o-", color="#4C72B0", linewidth=2.0,
        markersize=7, label="Átlagos hiba")
ax.fill_between(sigmas, mins, maxs, alpha=0.2, color="#4C72B0",
                label="Min–max tartomány")

ax.set_xlabel("RSSI-zaj σ [dB]", fontsize=12)
ax.set_ylabel("Lokalizációs hiba [m]", fontsize=12)
ax.set_title(
    f"RSSI-alapú lokalizációs hiba vs mérési zaj\n"
    f"4 anchor, 50×50 m terület, {N_TRIALS} Monte-Carlo trial, seed={SEED}",
    fontsize=11,
)
ax.legend(fontsize=10)
ax.grid(True, alpha=0.35)
ax.set_xticks(sigmas)

plt.tight_layout()
out_path = Path(__file__).parent.parent / "reports" / "figures" / "localization_error.png"
out_path.parent.mkdir(parents=True, exist_ok=True)
plt.savefig(out_path, dpi=150, bbox_inches="tight")
print(f"\nÁbra mentve: {out_path}")
plt.close()
