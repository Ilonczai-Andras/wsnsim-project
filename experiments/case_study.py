"""7.14. hét — Esettanulmány: Okos Mezőgazdaság (Smart Agriculture) WSN.

Ez a szcenárió egy 50 csomópontos, véletlenszerűen telepített mezőgazdasági
szenzorhálózatot szimulál. A csomópontok fa-topológiában (SinkTreeRouter)
továbbítják a talajnedvesség-adatokat a központi nyelőhöz.
A link szintű kommunikációt az ARQ és MAC réteg (EnergyModel) biztosítja.

A kísérlet a teljes hálózat várható PDR-jét és energiafogyasztását értékeli ki
különböző MAC backoff és ARQ retry_limit beállítások mellett, majd Pareto-szűréssel
választja ki a legjobb kompromisszumos megoldásokat.
"""

import math
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from wsnsim.utils.topology import random_deployment, build_neighbor_graph
from wsnsim.models.routing import SinkTreeRouter
from wsnsim.models.channel import LogDistanceChannel
from wsnsim.models.energy import EnergyModel
from wsnsim.models.mac import Medium
from wsnsim.models.packet import Packet
from wsnsim.models.reliability import ARQConfig, ARQLink, ARQStats
from wsnsim.models.optimization import ParameterGrid, ParetoFilter

def main():
    print("=== WSN Esettanulmány: Okos Mezőgazdaság ===")
    print("Hálózat generálása (50 csomópont, 100x100m terület)...")
    
    # 1. Topológia generálása
    RNG_SEED = 42
    rng = np.random.default_rng(RNG_SEED)
    nodes = random_deployment(n=50, area_m=100.0, rng=rng)
    
    # Középső csomópont legyen a sink
    distances_to_center = [(n.node_id, math.hypot(n.x - 50, n.y - 50)) for n in nodes]
    sink_id = min(distances_to_center, key=lambda x: x[1])[0]
    
    # 2. Szomszédsági gráf és Routing (Sink Tree)
    G = build_neighbor_graph(nodes, range_m=25.0)
    tree_router = SinkTreeRouter(G, sink_id=sink_id)
    
    avg_hops = 0.0
    reachable_nodes = 0
    for nid in G.nodes:
        if nid != sink_id:
            path = tree_router.path_to_sink(nid)
            if path:
                avg_hops += len(path) - 1 # edges = nodes - 1
                reachable_nodes += 1
                
    if reachable_nodes > 0:
        avg_hops /= reachable_nodes
        
    print(f"Elérhető csomópontok: {reachable_nodes}/49")
    print(f"Átlagos hop-távolság a nyelőhöz: {avg_hops:.2f}")
    
    # Átlagos link távolság becslése a fában
    avg_link_distance = np.mean([G[u][v]['distance'] for u, v in tree_router.tree_edges()])
    print(f"Átlagos fizikai link távolság: {avg_link_distance:.2f} m\n")

    # 3. Design Space Exploration (ARQ & MAC paraméterek)
    print("Tervezési tér feltérképezése (Design Space Exploration)...")
    param_dict = {
        "retry_limit": [0, 1, 2, 3, 5],
        "backoff_base_us": [1000.0, 5000.0, 10000.0]
    }
    
    grid = ParameterGrid(param_dict)
    N_PACKETS = 100 # packets per link simulation
    solutions = []
    
    for config in grid:
        channel = LogDistanceChannel(
            sigma_db=4.0, # Realisztikus kültéri shadowing
            rng=np.random.default_rng(RNG_SEED),
        )
        link_rng = np.random.default_rng(RNG_SEED)
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
            distance_m=avg_link_distance,
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
            current_us += result.total_tx_us + 50_000.0 # 50 ms gap

        link_pdr = stats.pdr()
        link_energy_mj = stats.mean_energy_j() * 1e3
        
        # Hálózati skálázás (közelítés):
        # A hálózati PDR a link PDR-ek szorzata a hopokon át
        # A hálózati energia az átlagos hop-szorosa a link energiának
        network_pdr = link_pdr ** avg_hops
        network_energy_mj = link_energy_mj * avg_hops
        
        solutions.append((config, (network_pdr, network_energy_mj)))

    # 4. Pareto Szűrés
    # Cél: Max PDR, Min Energia
    pf = ParetoFilter(("max", "min"))
    pareto_front = pf.filter(solutions)
    
    print("\n--- Pareto-optimális megoldások ---")
    pareto_front_sorted = sorted(pareto_front, key=lambda x: x[1][0])
    for sol in pareto_front_sorted:
        config, objs = sol
        print(f"Config: {config} => Net PDR: {objs[0]*100:.1f}%, Net Energy: {objs[1]:.2f} mJ")
        
    print("\n--- Döntés és Indoklás ---")
    print("Ebben a mezőgazdasági (Smart Agriculture) szenárióban a talajnedvesség "
          "és hőmérséklet értékek lassan változnak, a 100%-os megbízhatóság nem kritikus. "
          "Egy ~90-95%-os hálózati PDR már tökéletesen elegendő a helyes méréshez. ")
    
    best_sol = None
    for sol in pareto_front_sorted:
        if sol[1][0] >= 0.88:
            best_sol = sol
            break
            
    if best_sol:
        print(f"A választott 'legjobb' kompromisszum: {best_sol[0]}")
        print(f"Itt a PDR elfogadható ({best_sol[1][0]*100:.1f}%), miközben az energiafogyasztás "
              f"({best_sol[1][1]:.2f} mJ) jelentősen alacsonyabb, mint a 100% PDR-t biztosító extrémebb ARQ beállításoknál. "
              f"A retry_limit túlzott növelése (pl. 5) marginális PDR javulást hoz, de aránytalanul sokat fogyaszt a többszörös hiba miatti re-transzmissziók miatt.")
    
    # 5. Vizualizáció (Pareto front)
    pdrs_all = [sol[1][0]*100 for sol in solutions]
    energies_all = [sol[1][1] for sol in solutions]
    
    pdrs_pareto = [sol[1][0]*100 for sol in pareto_front_sorted]
    energies_pareto = [sol[1][1] for sol in pareto_front_sorted]
    
    os.makedirs("reports/figures", exist_ok=True)
    plt.figure(figsize=(10, 6))
    plt.scatter(pdrs_all, energies_all, c='lightgray', alpha=0.7, s=50, label='Kombinációs tér')
    plt.plot(pdrs_pareto, energies_pareto, 'r-o', linewidth=2, markersize=8, label='Pareto Front')
    
    if best_sol:
        plt.scatter([best_sol[1][0]*100], [best_sol[1][1]], c='blue', s=150, zorder=5, marker='*', label='Választott Konfiguráció')
    
    for sol in pareto_front_sorted:
        config, objs = sol
        label = f"r={config['retry_limit']},b={int(config['backoff_base_us']//1000)}ms"
        plt.annotate(label, (objs[0]*100, objs[1]), xytext=(5, -10), textcoords='offset points', fontsize=9)
    
    plt.title('Okos Mezőgazdaság Esettanulmány: PDR vs Energia (Pareto)')
    plt.xlabel('Hálózati PDR (%)')
    plt.ylabel('Hálózati Átlagos Energia / Csomag (mJ)')
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.legend()
    plt.tight_layout()
    plt.savefig('reports/figures/case_study_pareto.png', dpi=300)
    plt.close()
    
    print("\nÁbra generálva: reports/figures/case_study_pareto.png")

if __name__ == "__main__":
    main()
