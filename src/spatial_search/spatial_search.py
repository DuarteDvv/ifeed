"""Busca espacial, classificação por raio e estimativas pela malha viária"""

import osmnx as ox

from src.generation.rider_generation import filter_candidates_by_radius
from src.geo_index.geohash.geohashing import get_geohash_neighbors
from src.geometry.geometry_utilities import (
    EARTH_RADIUS,
    classify_candidates_by_distance,
    haversine_distance,
)

__all__ = [
    "EARTH_RADIUS",
    "select_geohash_prefix_size",
    "search_candidates",
    "haversine_distance",
    "classify_candidates_by_distance",
    "filter_candidates_by_radius",
    "osm_distance_and_time",
]


def select_geohash_prefix_size(radius_meters: float) -> int:
    "seleciona o tamanho de prefixo Geohash cuja grade 3x3 cobre integralmente o raio em metros"
    if radius_meters <= 600.0:
        return 6
    return 5


def search_candidates(tree, bar_geohash, prefix_size: int = 6):
    "retorna IDs da célula do bar e das oito vizinhas"
    if not bar_geohash:
        return []

    candidate_ids = []
    prefixes = [bar_geohash[:prefix_size]] + get_geohash_neighbors(bar_geohash, size=prefix_size)

    for prefix in prefixes:
        candidate_ids.extend(tree.search_prefix(prefix))

    return list(dict.fromkeys(candidate_ids))


def osm_distance_and_time(road_network, candidates, restaurant_location):
    "calcula rotas em lote, com distância em metros e tempo em minutos"

    if not candidates:
        return []

    bar_latitude, bar_longitude = restaurant_location
    longitudes = [bar_longitude] + [candidate["longitude"] for candidate in candidates]
    latitudes = [bar_latitude] + [candidate["latitude"] for candidate in candidates]

    # o primeiro nó é o bar. os demais são os entregadores, na ordem de entrada
    nodes = ox.distance.nearest_nodes(road_network, X=longitudes, Y=latitudes)
    bar_node = nodes[0]
    rider_nodes = list(nodes[1:])

    routes = ox.routing.shortest_path(
        road_network,
        orig=rider_nodes,
        dest=[bar_node] * len(rider_nodes),
        weight="travel_time",
    )

    results = []
    for candidate, route in zip(candidates, routes):
        result = {**candidate, "road_distance": None, "estimated_time": None}

        if route is not None:
            if len(route) == 1:
                result["road_distance"] = 0.0
                result["estimated_time"] = 0.0
            else:
                total_length = 0.0
                total_travel_time = 0.0
                for u, v in zip(route[:-1], route[1:]):
                    edge_dict = road_network[u][v]
                    best_edge = min(
                        edge_dict.values(),
                        key=lambda d: d.get("travel_time", float("inf")),
                    )
                    total_length += best_edge.get("length", 0.0)
                    total_travel_time += best_edge.get("travel_time", 0.0)

                result["road_distance"] = round(float(total_length), 2)
                result["estimated_time"] = round(float(total_travel_time) / 60, 2)

        results.append(result)
    return results
