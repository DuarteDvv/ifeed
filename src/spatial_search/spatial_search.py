"""Busca espacial, classificação por raio e estimativas pela malha viária."""

import osmnx as ox

from src.geo_index.geohash.geohashing import get_geohash_neighbors

EARTH_RADIUS = 6_371_000  # metros


def search_candidates(tree, bar_geohash):
    """Retorna IDs únicos da célula do bar e das oito vizinhas, com prefixo 6"""
    if not bar_geohash:
        return []

    candidate_ids = []
    prefixes = [bar_geohash[:6]] + get_geohash_neighbors(bar_geohash)

    for prefix in prefixes:
        candidate_ids.extend(tree.search_prefix(prefix))

    return list(dict.fromkeys(candidate_ids))


def haversine_distance(lat1, lon1, lat2, lon2):
    """distância geométrica em metros usando Haversine do OSMnx"""

    return float(ox.distance.great_circle(lat1, lon1, lat2, lon2, earth_radius=EARTH_RADIUS))


def classify_candidates(candidates, restaurant_location, radius):
    """Classifica entregadores por Haversine, com raio informado em metros."""
    results = []
    for rider in candidates:
        
        distance = haversine_distance(
            restaurant_location[0], restaurant_location[1], rider.latitude, rider.longitude
        )
        
        results.append({
            "id": rider.id,
            "latitude": rider.latitude,
            "longitude": rider.longitude,
            "distance": round(distance, 2),
            "within_range": distance <= radius,
        })

    return results


def osm_distance_and_time(road_network, candidates, restaurant_location):
    """Adiciona distância em metros e tempo em minutos da rota mais rápida.
    """

    bar_latitude, bar_longitude = restaurant_location
    bar_node = ox.distance.nearest_nodes(road_network, X=bar_longitude, Y=bar_latitude)

    results = []
    for candidate in candidates:
        rider_node = ox.distance.nearest_nodes(
            road_network, X=candidate["longitude"], Y=candidate["latitude"]
        )

        route = ox.routing.shortest_path(
            road_network, rider_node, bar_node, weight="travel_time"
        )

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
