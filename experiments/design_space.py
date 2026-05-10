"""7.13. Design Space Exploration with Pareto Front.

Sweeps parameters: retry_limit, distance_m, backoff_base_us.
Computes PDR (max) and mean_energy_mj (min) and finds Pareto-optimal configurations.
"""

import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from wsnsim.models.channel import LogDistanceChannel
from wsnsim.models.energy import EnergyModel
from wsnsim.models.mac import Medium
from wsnsim.models.packet import Packet
from wsnsim.models.reliability import ARQConfig, ARQLink, ARQStats
from wsnsim.models.optimization import ParameterGrid, ParetoFilter, ConfigDumper

def main():
    param_dict = {
        "retry_limit": [0, 1, 3, 5],
        "distance_m": [10, 20, 30, 40, 50],
        "backoff_base_us": [1000.0, 5000.0, 10000.0]
    }
    
    grid = ParameterGrid(param_dict)
    print(f"Total configurations to evaluate: {len(grid)}")
    
    N_PACKETS = 50
    MASTER_SEED = 42
    
    solutions = []
    
    for config in grid:
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
            distance_m=config["distance_m"],
            config=ARQConfig(
                retry_limit=config["retry_limit"],
                backoff_base_us=config["backoff_base_us"]
            ),
            rng=link_rng,
        )

        stats = ARQStats()
        current_us = 0.0
        for i in range(N_PACKETS):
            pkt = Packet(packet_id=i, src=0, dst=1, size_bytes=32)
            result = link.transmit(pkt, at_us=current_us)
            stats.add(result)
            current_us += result.total_tx_us + 1_000.0

        pdr = stats.pdr()
        mean_energy_mj = stats.mean_energy_j() * 1e3
        
        solutions.append((config, (pdr, mean_energy_mj)))
        
    pf = ParetoFilter(("max", "min"))
    pareto_front = pf.filter(solutions)
    
    # Print results
    print(f"Found {len(pareto_front)} Pareto-optimal configurations:")
    for sol in pareto_front:
        config, objs = sol
        print(f"Config: {config} => PDR: {objs[0]:.3f}, Energy: {objs[1]:.3f} mJ")
        
    os.makedirs("reports/figures", exist_ok=True)
    
    # Plotting
    pdrs_all = [sol[1][0] for sol in solutions]
    energies_all = [sol[1][1] for sol in solutions]
    
    # Sort Pareto front by PDR for line plotting
    pareto_front_sorted = sorted(pareto_front, key=lambda x: x[1][0])
    pdrs_pareto = [sol[1][0] for sol in pareto_front_sorted]
    energies_pareto = [sol[1][1] for sol in pareto_front_sorted]
    
    plt.figure(figsize=(10, 6))
    plt.scatter(pdrs_all, energies_all, c='lightgray', alpha=0.7, label='All Configurations')
    plt.plot(pdrs_pareto, energies_pareto, 'r-o', linewidth=2, markersize=8, label='Pareto Front')
    
    for idx, sol in enumerate(pareto_front_sorted):
        config, objs = sol
        label = f"r={config['retry_limit']},d={config['distance_m']},b={int(config['backoff_base_us'])}"
        plt.annotate(label, (objs[0], objs[1]),
                    xytext=(5, 5 + idx * 12),
                    textcoords='offset points', fontsize=7)
    
    plt.title('Design Space Exploration: Reliability vs Energy')
    plt.xlabel('Packet Delivery Ratio (PDR)')
    plt.ylabel('Mean Energy per Packet (mJ)')
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.legend()
    plt.tight_layout()
    plt.savefig('reports/figures/design_space.png', dpi=300)
    plt.close()
    
    print(f"Plot saved to reports/figures/design_space.png")

if __name__ == "__main__":
    main()
