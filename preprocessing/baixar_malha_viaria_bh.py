#!/usr/bin/env python3
"""Baixa uma única vez o grafo de ruas transitáveis de Belo Horizonte
"""

from pathlib import Path
import osmnx as ox


def main():
    road_network_path = Path(__file__).resolve().parents[1] / "data" / "malha_viaria_bh.graphml"

    if road_network_path.is_file():
        print(f"Grafo já existe: {road_network_path}. Download dispensado.")
        return

    road_network_path.parent.mkdir(parents=True, exist_ok=True)
    ox.settings.cache_folder = road_network_path.parent / ".osmnx_cache"

    print("Baixando a malha viária de Belo Horizonte...")
    road_network = ox.graph_from_place(
        "Belo Horizonte, Minas Gerais, Brazil",
        network_type="drive",
        simplify=True,
    )


    temporary_path = road_network_path.with_suffix(".graphml.tmp")
    try:
        ox.save_graphml(road_network, filepath=temporary_path)
        temporary_path.replace(road_network_path)
    finally:
        temporary_path.unlink(missing_ok=True)

    print(f"Grafo salvo em: {road_network_path}")
    print(f"Nós: {road_network.number_of_nodes()}; arestas: {road_network.number_of_edges()}")


if __name__ == "__main__":
    main()
