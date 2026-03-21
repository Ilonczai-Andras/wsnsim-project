"""MAC protokoll összehasonlítás: ALOHA vs CSMA ütközési arány és átbocsátás.

Szcenárió
---------
N_NODES csomópont egyenként p_tx valószínűséggel küld egy-egy csomagot
minden szimulációs körben (Bernoulli arrivals). Az egyidejű küldők száma
k ~ Binomial(N, p) mintánként.

Két protokoll futtatása azonos forgalomgenerálással:
  • **ALOHA**: azonnali küldés, carrier-sense nélkül; átfedő adások ütköznek.
  • **CSMA/BEB**: a csatornát figyelő + backoff stratégia; a csatorna
    foglaltsága esetén vár, ütközés esetén exponenciálisan növeli a CW-t.

Kimenet
-------
Konzol: táblázat (G, ALOHA throughput, CSMA throughput, ALOHA PDR, CSMA PDR)
Ábra:   reports/figures/mac_comparison.png
  – Bal panel: normalizált átbocsátás S vs kínált forgalom G
  – Jobb panel: PDR (Packet Delivery Ratio) vs G
  – ALOHA analitikus görbe (klasszikus unslotted képlet: S = G·e^{-2G})

Seed: 42 (reprodukálható)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

from wsnsim.models.mac import ALOHAMac, CSMAMac, Medium
from wsnsim.models.packet import Packet

# ── Paraméterek ─────────────────────────────────────────────────────────────
SEED = 42
N_NODES = 10            # csomópontok száma
N_ROUNDS = 2_000        # szimulációs körök száma
TX_DUR_US = 4_000.0     # 32 bájt @ 250 kbps = 4 ms
SLOT_US = 1_000.0       # 1 ms backoff slot (CSMA)
CW_MIN = 8
CW_MAX = 128
MAX_RETRIES = 5
JITTER_US = 500.0       # véletlenszerű időzítési jitter (µs); << TX_DUR

# p_tx értékek → ajánlott forgalom G = N * p_tx
P_TX_VALUES = np.array([0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7,
                          0.8, 0.9, 1.0])

FIG_PATH = (
    Path(__file__).parent.parent / "reports" / "figures" / "mac_comparison.png"
)


# ── Szimulációs segédfüggvények ──────────────────────────────────────────────

def _make_packet(i: int) -> Packet:
    return Packet(packet_id=i, src=i, dst=0)


def simulate_aloha(n_nodes: int, p_tx: float,
                   n_rounds: int, rng: np.random.Generator) -> tuple[float, float]:
    """Szimulálja az ALOHA protokollt.

    Returns
    -------
    (throughput, pdr)
        throughput: sikeres csomagok / összes kör (normalizált)
        pdr:        sikeres csomagok / elküldött csomagok
    """
    total_sent = 0
    total_success = 0

    for _ in range(n_rounds):
        # Kik küldenek ebben a körben?
        mask = rng.random(n_nodes) < p_tx
        senders = np.where(mask)[0]
        if len(senders) == 0:
            continue

        medium = Medium()
        mac = ALOHAMac(medium=medium, tx_duration_us=TX_DUR_US)
        pkts = {i: _make_packet(int(i)) for i in senders}

        # Kis véletlen jitter a valóságszerűség kedvéért
        arrivals = rng.uniform(0.0, JITTER_US, size=len(senders))
        for j, i in enumerate(senders):
            mac.send(int(i), pkts[i], at_us=float(arrivals[j]))

        # Statisztika
        success = sum(1 for p in pkts.values() if not p.collided)
        total_sent += len(senders)
        total_success += success

    throughput = total_success / n_rounds
    pdr = total_success / total_sent if total_sent > 0 else 0.0
    return throughput, pdr


def simulate_csma(n_nodes: int, p_tx: float,
                  n_rounds: int, rng: np.random.Generator) -> tuple[float, float]:
    """Szimulálja a CSMA/BEB protokollt.

    Returns
    -------
    (throughput, pdr)
    """
    total_sent = 0
    total_success = 0

    for _ in range(n_rounds):
        mask = rng.random(n_nodes) < p_tx
        senders = np.where(mask)[0]
        if len(senders) == 0:
            continue

        medium = Medium()
        mac = CSMAMac(
            medium=medium,
            tx_duration_us=TX_DUR_US,
            slot_us=SLOT_US,
            cw_min=CW_MIN,
            cw_max=CW_MAX,
            max_retries=MAX_RETRIES,
            rng=rng,
        )
        pkts = {i: _make_packet(int(i)) for i in senders}

        # Küldők érkezési sorrendben dolgoznak fel (carrier sense)
        arrivals = rng.uniform(0.0, JITTER_US, size=len(senders))
        order = np.argsort(arrivals)
        for oi in order:
            i = senders[oi]
            mac.send(int(i), pkts[i], at_us=float(arrivals[oi]))

        success = sum(1 for p in pkts.values() if not p.collided)
        total_sent += len(senders)
        total_success += success

    throughput = total_success / n_rounds
    pdr = total_success / total_sent if total_sent > 0 else 0.0
    return throughput, pdr


# ── Fő futtatás ──────────────────────────────────────────────────────────────

def main() -> None:
    rng = np.random.default_rng(SEED)

    g_values = N_NODES * P_TX_VALUES
    aloha_tp, aloha_pdr = [], []
    csma_tp, csma_pdr = [], []

    print(f"{'G':>5}  {'p_tx':>5}  {'ALOHA-S':>8}  {'CSMA-S':>8}  "
          f"{'ALOHA-PDR':>10}  {'CSMA-PDR':>9}")
    print("-" * 58)

    for p, g in zip(P_TX_VALUES, g_values):
        a_tp, a_pdr = simulate_aloha(N_NODES, p, N_ROUNDS, rng)
        c_tp, c_pdr = simulate_csma(N_NODES, p, N_ROUNDS, rng)

        aloha_tp.append(a_tp)
        csma_tp.append(c_tp)
        aloha_pdr.append(a_pdr)
        csma_pdr.append(c_pdr)

        print(f"{g:>5.2f}  {p:>5.2f}  {a_tp:>8.4f}  {c_tp:>8.4f}  "
              f"{a_pdr:>10.4f}  {c_pdr:>9.4f}")

    # ── Analitikus ALOHA görbe ────────────────────────────────────────────────
    g_fine = np.linspace(0.01, N_NODES, 200)
    # Unslotted ALOHA: S = G · e^{-2G}  (max @ G=0.5 → S≈0.184)
    aloha_analytic_tp = g_fine * np.exp(-2 * g_fine)

    # ── Ábra ─────────────────────────────────────────────────────────────────
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))
    fig.suptitle(
        f"MAC protokoll összehasonlítás — ALOHA vs CSMA\n"
        f"(N={N_NODES} node, {N_ROUNDS} kör, seed={SEED})",
        fontsize=11,
    )

    # Bal panel: normalizált átbocsátás S vs G
    ax1.plot(g_fine, aloha_analytic_tp, "k--", lw=1.2,
             label="ALOHA analitikus $G e^{-2G}$")
    ax1.plot(g_values, aloha_tp, "o-", color="tab:red", lw=1.8,
             label="ALOHA szim.")
    ax1.plot(g_values, csma_tp, "s-", color="tab:blue", lw=1.8,
             label="CSMA/BEB szim.")
    ax1.set_xlabel("Kínált forgalom G (csomag/kör)")
    ax1.set_ylabel("Normalizált átbocsátás S")
    ax1.set_title("Átbocsátás vs. kínált forgalom")
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.4)
    ax1.set_xlim(0, N_NODES)
    ax1.set_ylim(0, None)

    # Jobb panel: PDR vs G
    ax2.plot(g_values, aloha_pdr, "o-", color="tab:red", lw=1.8,
             label="ALOHA PDR")
    ax2.plot(g_values, csma_pdr, "s-", color="tab:blue", lw=1.8,
             label="CSMA/BEB PDR")
    ax2.set_xlabel("Kínált forgalom G (csomag/kör)")
    ax2.set_ylabel("PDR (sikeres / elküldött)")
    ax2.set_title("Csomag kézbesítési arány vs. forgalom")
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.4)
    ax2.set_xlim(0, N_NODES)
    ax2.set_ylim(0, 1.05)

    plt.tight_layout()
    FIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_PATH, dpi=150)
    plt.close(fig)
    print(f"\nÁbra mentve: {FIG_PATH}")


if __name__ == "__main__":
    main()
