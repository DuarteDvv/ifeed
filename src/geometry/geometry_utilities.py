"""Módulo centralizado de utilidades de geometria computacional e espacial."""

import math
import numpy as np
import osmnx as ox
from shapely.geometry import LineString, Point

EARTH_RADIUS = 6_371_000  # metros

__all__ = [
    "split_at_middle",
    "hypot",
    "squared_distance",
    "haversine_distance",
    "classify_candidates",
    "median_geometric",
    "unpack_point",
    "get_axis_coord",
    "split_points_by_median",
    "EARTH_RADIUS",
]



def hypot(dx, dy):
    "calcula a hipotenusa sqrt(dx^2 + dy^2)"
    return math.sqrt(dx * dx + dy * dy)


def squared_distance(coord_a, coord_b):
    "calcula a distância euclidiana ao quadrado entre dois pontos"
    return sum((a - b) ** 2 for a, b in zip(coord_a, coord_b))


def haversine_distance(lat1, lon1, lat2, lon2):
    "distância geométrica em metros usando Haversine do OSMnx"
    return float(ox.distance.great_circle(lat1, lon1, lat2, lon2, earth_radius=EARTH_RADIUS))


def classify_candidates(candidates, restaurant_location, radius):
    """Classifica entregadores por Haversine, com raio informado em metros."""
    results = []
    for rider in candidates:
        r_id = getattr(rider, "id", None) if not isinstance(rider, dict) else rider.get("id")
        r_lat = getattr(rider, "latitude", None) if not isinstance(rider, dict) else rider.get("latitude")
        r_lon = getattr(rider, "longitude", None) if not isinstance(rider, dict) else rider.get("longitude")

        distance = haversine_distance(
            restaurant_location[0], restaurant_location[1], r_lat, r_lon
        )

        results.append({
            "id": r_id,
            "latitude": r_lat,
            "longitude": r_lon,
            "distance": round(distance, 2),
            "within_range": distance <= radius,
        })

    return results


def split_at_middle(geom):
    "divide uma rua no seu ponto médio, mesmo que ela seja curva"

    if hasattr(geom, "coords"): # se for uma linestring do shapely
        coords = list(geom.coords)
    elif isinstance(geom, (list, tuple)): # se for uma lista/tupla de coordenadas
        coords = list(geom)
    else:
        raise TypeError(f"geometria inválida: {type(geom)}")

    # calcula os comprimentos de cada subsegmento usando hypot
    segment_lengths = [
        hypot(coords[i + 1][0] - coords[i][0], coords[i + 1][1] - coords[i][1])
        for i in range(len(coords) - 1)
    ]

    total_length = sum(segment_lengths)
    half_length = total_length / 2.0
    accumulated = 0.0

    # percorre os segmentos para identificar onde cai a distância da metade
    for i, seg_len in enumerate(segment_lengths):
        if accumulated + seg_len >= half_length or i == len(segment_lengths) - 1:
            # distância restante a percorrer dentro do segmento atual
            seg_dist = half_length - accumulated
            fraction = (seg_dist / seg_len) if seg_len > 0.0 else 0.0
            fraction = max(0.0, min(1.0, fraction))

            # acha as coordenadas (x, y) do ponto médio
            x1, y1 = coords[i]
            x2, y2 = coords[i + 1]
            mx = x1 + fraction * (x2 - x1)
            my = y1 + fraction * (y2 - y1)
            ponto = Point(mx, my)

            # divide a lista de vértices nas duas metades, evitando vértices duplicados nas bordas
            if fraction >= 1.0 - 1e-9:
                # o ponto médio coincide com o vértice final do segmento
                c_esq = coords[:i + 2]
                c_dir = coords[i + 1:]
            elif fraction <= 1e-9:
                # o ponto médio coincide com o vértice inicial do segmento
                c_esq = coords[:i + 1]
                c_dir = coords[i:]
            else:
                # o ponto médio está no interior do segmento
                mid_pt = (mx, my)
                c_esq = coords[:i + 1] + [mid_pt]
                c_dir = [mid_pt] + coords[i + 1:]

            # TODO
            # # garante que as sub-geometrias tenham pelo menos dois vértices válidos
            # if len(c_esq) < 2:
            #     c_esq = [c_esq[0], c_esq[0]]
            # if len(c_dir) < 2:
            #     c_dir = [c_dir[0], c_dir[0]]

            return ponto, LineString(c_esq), LineString(c_dir)

        accumulated += seg_len

    # fallback para o último vértice
    ponto = Point(coords[-1][0], coords[-1][1])
    return ponto, geom, geom


def median_geometric(points):
    "algoritmo de Weiszfeld em coordenadas UTM (metros)."

    pts = np.asarray(points, dtype=float)
    if len(pts) == 1:
        return pts[0]
    estimate = np.median(pts, axis=0)
    for _ in range(300):
        distances = np.linalg.norm(pts - estimate, axis=1)
        if np.min(distances) < 1e-8:
            return pts[np.argmin(distances)]
        weights = 1.0 / distances
        new = (pts * weights[:, None]).sum(axis=0) / weights.sum()
        if np.linalg.norm(new - estimate) < 1e-7:
            return new
        estimate = new
    return estimate


# ==============================================================================
# 4. Particionamento Espacial e Eixos
# ==============================================================================

def unpack_point(item):
    "separa as coordenadas dos dados adicionais associados ao ponto"
    if hasattr(item, "coords"):
        return item.coords, getattr(item, "data", None)

    if isinstance(item, (tuple, list)) and len(item) == 2 and isinstance(item[0], (tuple, list)):
        return tuple(item[0]), item[1]

    if isinstance(item, (tuple, list)):
        return tuple(item), None

    return item, None


def get_axis_coord(item, axis):
    "obtém o valor da coordenada no eixo fornecido"
    coords, _ = unpack_point(item)
    return coords[axis]


def split_points_by_median(points, axis):
    "particiona pontos pela mediana ao longo do eixo fornecido"
    mid = len(points) // 2
    if len(points) <= 1:
        return [], points[0], []

    # escolhendo a coordenada do eixo atual para ordenar baseado nela
    dtype = [("coord", float), ("item", object)]
    pairs = np.empty(len(points), dtype=dtype)
    for i, p in enumerate(points):
        pairs[i] = (get_axis_coord(p, axis), p)

    partitioned = np.partition(pairs, mid, order="coord")

    left_points = list(partitioned[:mid]["item"])
    median_item = partitioned[mid]["item"]
    right_points = list(partitioned[mid + 1:]["item"])

    return left_points, median_item, right_points