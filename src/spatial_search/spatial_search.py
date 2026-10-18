"""Busca espacial, classificação por raio e estimativas pela malha viária."""

import osmnx as ox

from src.geo_index.geohash.geohashing import get_geohash_neighbors
from src.geometry.geometry_utilities import (
    EARTH_RADIUS,
    classify_candidates_by_distance,
    haversine_distance,
)

__all__ = [
    "EARTH_RADIUS",
    "search_candidates",
    "haversine_distance",
    "classify_candidates_by_distance",
    "osm_distance_and_time",
]


def search_candidates(tree, bar_geohash):
    """Retorna IDs únicos da célula do bar e das oito vizinhas, com prefixo 6"""
    if not bar_geohash:
        return []

    candidate_ids = []
    prefixes = [bar_geohash[:6]] + get_geohash_neighbors(bar_geohash)

    for prefix in prefixes:
        candidate_ids.extend(tree.search_prefix(prefix))

    return list(dict.fromkeys(candidate_ids))


def osm_distance_and_time(road_network, candidates, restaurant_location):
    """Calcula rotas em lote, com distância em metros e tempo em minutos."""
    if not candidates:
        return []

    bar_latitude, bar_longitude = restaurant_location
    longitudes = [bar_longitude] + [candidate["longitude"] for candidate in candidates]
    latitudes = [bar_latitude] + [candidate["latitude"] for candidate in candidates]

    # O primeiro nó é o bar; os demais são os entregadores, na ordem de entrada.
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
                edges = ox.routing.route_to_gdf(road_network, route, weight="travel_time")
                result["road_distance"] = round(float(edges["length"].sum(skipna=False)), 2)
                result["estimated_time"] = round(float(edges["travel_time"].sum(skipna=False)) / 60, 2)

        results.append(result)
    return results
