"""7.7. hét — ARQ sweep: retry_limit × távolság PDR és energia elemzés.

Paraméter sweep:
  retry_limit ∈ {0, 1, 2, 3, 5}   (újraküldések max. száma)
  distance_m  ∈ [5, 10, 20, 30, 40, 50]  (pont-pont link távolsága)

Minden kombinációra 200 csomag átvitele ARQLink-en, ARQStats-ba gyűjtve.

Kimenet:
  - stdout táblázat: retry_limit | distance_m | PDR | mean_attempts | mean_energy_mJ
  - reports/figures/arq_sweep.png : 2 panel
       Bal:  PDR vs távolság (retry_limit-enkénti vonalak)
       Jobb: Átlagos energia/csomag (mJ) vs távolság

Reprodukálhatóság: minden (retry_limit, distance_m) kombináció fix seed=42-vel indul.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from wsnsim.models.channel import LogDistanceChannel
from wsnsim.models.energy import EnergyModel
from wsnsim.models.mac import Medium
from wsnsim.models.packet import Packet
from wsnsim.models.reliability import ARQConfig, ARQLink, ARQStats

# ---------------------------------------------------------------------------
# Konfigurálható paraméterek
# ---------------------------------------------------------------------------

RETRY_LIMITS = [0, 1, 2, 3, 5]
DISTANCES_M = [5, 10, 20, 30, 40, 50]
N_PACKETS = 200
MASTER_SEED = 42

# ---------------------------------------------------------------------------
# Sweep futtatás
# ---------------------------------------------------------------------------

records: list[dict] = []

for rl in RETRY_LIMITS:
    for d_m in DISTANCES_M:
        # Minden kombinációhoz azonos seed → reprodukálható
        channel = LogDistanceChannel(
            sigma_db=3.0,
            rng=np.random.default_rng(MASTER_SEED),
        )
        link_rng = np.random.default_rng(MASTER_SEED)
        energy_src = EnergyModel(node_id=0)
        energy_dst = EnergyModel(node_id=1)
        medium = Medium()

        link = ARQLink(
            src=0,
            dst=1,
            channel=channel,
            energy_src=energy_src,
            energy_dst=energy_dst,
            medium=medium,
            distance_m=d_m,
            config=ARQConfig(retry_limit=rl),
            rng=link_rng,
        )

        stats = ARQStats()
        current_us = 0.0
        for i in range(N_PACKETS):
            pkt = Packet(packet_id=i, src=0, dst=1, size_bytes=32)
            result = link.transmit(pkt, at_us=current_us)
            stats.add(result)
            current_us += result.total_tx_us + 1_000.0  # 1 ms gap the két csomag között

        records.append({
            "retry_limit": rl,
            "distance_m": d_m,
            "pdr": stats.pdr(),
            "mean_attempts": stats.mean_attempts(),
            "mean_energy_mj": stats.mean_energy_j() * 1e3,  # J → mJ
        })

# ---------------------------------------------------------------------------
# Stdout táblázat
# ---------------------------------------------------------------------------

header = f"{'retry':>6} | {'dist_m':>7} | {'PDR':>6} | {'mean_att':>9} | {'energy_mJ':>10}"
sep = "-" * len(header)
print("\n=== ARQ Sweep eredmények ===")
print(header)
print(sep)
for row in records:
    print(
        f"{row['retry_limit']:>6} | {row['distance_m']:>7.0f} | "
        f"{row['pdr']:>6.3f} | {row['mean_attempts']:>9.2f} | "
        f"{row['mean_energy_mj']:>10.4f}"
    )

# ---------------------------------------------------------------------------
# Ábra generálás
# ---------------------------------------------------------------------------

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
fig.suptitle(
    f"ARQ sweep — {N_PACKETS} csomag/kombináció, LogDistanceChannel σ=3 dB, seed={MASTER_SEED}",
    fontsize=12,
)

colors = plt.cm.plasma(np.linspace(0.1, 0.9, len(RETRY_LIMITS)))
markers = ["o", "s", "^", "D", "v"]

for idx, rl in enumerate(RETRY_LIMITS):
    rows = [r for r in records if r["retry_limit"] == rl]
    ds = [r["distance_m"] for r in rows]
    pdrs = [r["pdr"] for r in rows]
    energies = [r["mean_energy_mj"] for r in rows]
    label = f"retry={rl}"

    ax1.plot(ds, pdrs, marker=markers[idx], color=colors[idx],
             linewidth=1.8, markersize=6, label=label)
    ax2.plot(ds, energies, marker=markers[idx], color=colors[idx],
             linewidth=1.8, markersize=6, label=label)

# Bal panel — PDR
ax1.set_xlabel("Távolság (m)")
ax1.set_ylabel("PDR")
ax1.set_title("PDR vs távolság (retry_limit-enkénti vonalak)")
ax1.set_ylim(-0.05, 1.10)
ax1.axhline(1.0, color="gray", linestyle="--", linewidth=0.8, alpha=0.6, label="Ideális")
ax1.legend(fontsize=9, loc="lower left")
ax1.grid(True, alpha=0.3)

# Jobb panel — energia
ax2.set_xlabel("Távolság (m)")
ax2.set_ylabel("Átlagos energia/csomag (mJ)")
ax2.set_title("Energia vs távolság (forrás node, delta/csomag)")
ax2.legend(fontsize=9)
ax2.grid(True, alpha=0.3)

plt.tight_layout()
out_path = Path(__file__).parent.parent / "reports" / "figures" / "arq_sweep.png"
out_path.parent.mkdir(parents=True, exist_ok=True)
plt.savefig(out_path, dpi=150, bbox_inches="tight")
print(f"\nÁbra mentve: {out_path}")
plt.close()
