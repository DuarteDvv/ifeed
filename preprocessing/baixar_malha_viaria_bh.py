#!/usr/bin/env python3
"""Baixa o grafo de Belo Horizonte e salva velocidades e tempos de viagem.
"""

import os
import osmnx as ox


def main():
    road_network_path = "data/malha_viaria_bh.graphml"
    os.makedirs("data", exist_ok=True)
    ox.settings.cache_folder = "data/.osmnx_cache"

    if os.path.isfile(road_network_path):
        print("Carregando a malha viária já salva...")
        road_network = ox.load_graphml(filepath=road_network_path)
    else:
        print("Baixando a malha viária de Belo Horizonte...")
        road_network = ox.graph_from_place(
            "Belo Horizonte, Minas Gerais, Brazil",
            network_type="drive",
            simplify=True,
        )

    print("Adicionando velocidades e tempos de viagem...")
    road_network = ox.routing.add_edge_speeds(road_network)
    road_network = ox.routing.add_edge_travel_times(road_network)

    temporary_path = road_network_path + ".tmp"
    try:
        ox.save_graphml(road_network, filepath=temporary_path)
        os.replace(temporary_path, road_network_path)
    finally:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)

    print(f"Grafo salvo em: {road_network_path}")
    print(f"Nós: {road_network.number_of_nodes()}; arestas: {road_network.number_of_edges()}")


if __name__ == "__main__":
    main()
