"""geração e distribuição espacial de entregadores em torno de bares"""

import csv
import gzip
from typing import Any, Iterable
import numpy as np
import osmnx as ox

from src.generation.kd_tree.KD_Tree import KDTree
from src.geo_index.geohash.geohashing import geohash_encode
from src.geometry.geometry_utilities import project_point_on_street
from src.models.Bar import Bar
from src.models.Rider import Rider

METERS_PER_DEGREE = 111_139.0
DEFAULT_SEGMENTS_PATH = "data/segmentos_ruas_bh.csv.gz"
DEFAULT_GRAPH_PATH = "data/malha_viaria_bh.graphml"

# caches em memória para evitar reconstrução da kd-tree e releitura da malha em múltiplas chamadas
_CACHED_KDTREES: dict[str, KDTree] = {}
_CACHED_STREET_GEOMETRIES: dict[str, dict[str, tuple[tuple[float, float], ...]]] = {}


def filter_valid_bars(bars: Iterable[Bar]) -> list[Bar]:
    "filtra e retorna apenas bares que possuem latitude e longitude definidas"
    return [
        bar for bar in bars
        if bar.latitude is not None and bar.longitude is not None
    ]


def filter_candidates_by_radius(candidates: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    "retorna apenas os dicionários de candidatos que estejam dentro do raio de atendimento"

    filtered: list[dict[str, Any]] = []
    for cand in candidates:
        if not isinstance(cand, dict):
            continue

        if cand.get("within_range", True):
            filtered.append(cand)

    return filtered


def calculate_bar_quotas(
    num_riders: int,
    num_bars: int,
    rng: np.random.Generator | None = None,
) -> list[int]:
    """calcula a quantidade de entregadores para cada bar de forma equilibrada.

    caso haja entregadores restantes, eles são distribuídos aleatoriamente entre os bares.
    """
    if num_riders <= 0 or num_bars <= 0:
        return [0] * max(0, num_bars)

    base_count = num_riders // num_bars
    remainder = num_riders % num_bars

    quotas = [base_count] * num_bars
    if remainder > 0:
        if rng is None:
            rng = np.random.default_rng()
        extra_bar_indices = rng.choice(num_bars, size=remainder, replace=False)
        for idx in extra_bar_indices:
            quotas[int(idx)] += 1

    return quotas


def sample_normal_coordinates(
    center_lat: float,
    center_lon: float,
    count: int,
    std_dev_meters: float,
    rng: np.random.Generator,
) -> list[tuple[float, float]]:
    "gera coordenadas com variação normal em metros em torno de um ponto central"
    if count <= 0:
        return []

    std_dev_deg = std_dev_meters / METERS_PER_DEGREE
    dlat = rng.normal(0.0, std_dev_deg, size=count)
    dlon = rng.normal(0.0, std_dev_deg, size=count)

    # limita as coordenadas aos intervalos geográficos válidos e converte para float nativo
    lats = np.clip(center_lat + dlat, -90.0, 90.0).tolist()
    lons = np.clip(center_lon + dlon, -180.0, 180.0).tolist()

    return list(zip(lats, lons))


def build_rider(
    rider_id: int,
    latitude: float,
    longitude: float,
    geohash_size: int = 8,
) -> Rider:
    "instancia um rider com suas coordenadas e geohash calculado"
    rider_geohash = geohash_encode(latitude, longitude, size=geohash_size)
    return Rider(
        id=rider_id,
        latitude=latitude,
        longitude=longitude,
        geohash=rider_geohash,
    )


def extract_street_coords(
    u: Any,
    v: Any,
    edge_data: dict[str, Any],
    nodes: Any,
) -> tuple[tuple[float, float], ...]:
    "extrai a sequência de vértices que compõem a geometria de uma rua"

    geom = edge_data.get("geometry")
    if geom is not None and hasattr(geom, "coords"):
        # no grafo do osmnx, geom.coords armazena pares na ordem (longitude, latitude)
        return tuple((float(lat), float(lon)) for lon, lat in geom.coords)

    # caso não haja geometria explicitamente, a rua é o segmento entre os nós u e v
    u_node = nodes[u]
    v_node = nodes[v]
    return (
        (float(u_node["y"]), float(u_node["x"])),
        (float(v_node["y"]), float(v_node["x"])),
    )


def build_street_geometries_map(
    road_network: Any,
) -> dict[str, tuple[tuple[float, float], ...]]:
    "constrói um dicionário mapeando o edge_id de cada rua para os seus vértices"

    nodes = road_network.nodes
    street_geometries: dict[str, tuple[tuple[float, float], ...]] = {}

    for u, v, k, data in road_network.edges(keys=True, data=True):
        edge_id = f"{u}_{v}_{k}"
        street_geometries[edge_id] = extract_street_coords(u, v, data, nodes)

    return street_geometries


def get_street_geometries(
    road_network: Any = None,
    graph_path: str = DEFAULT_GRAPH_PATH,
) -> dict[str, tuple[tuple[float, float], ...]]:
    "obtém e armazena em cache o dicionário de geometrias das ruas da malha viária"

    if graph_path in _CACHED_STREET_GEOMETRIES:
        return _CACHED_STREET_GEOMETRIES[graph_path]

    if road_network is None:
        road_network = ox.load_graphml(filepath=graph_path)

    street_geometries = build_street_geometries_map(road_network)
    _CACHED_STREET_GEOMETRIES[graph_path] = street_geometries
    return street_geometries


def load_segmentation_points(
    segments_path: str = DEFAULT_SEGMENTS_PATH,
) -> list[tuple[tuple[float, float], str]]:
    "carrega os pontos de segmentação de ruas e seus respectivos edge_id a partir do csv"

    points: list[tuple[tuple[float, float], str]] = []

    open_fn = gzip.open if segments_path.endswith(".gz") else open
    with open_fn(segments_path, mode="rt", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            lat = float(row["latitude"])
            lon = float(row["longitude"])
            edge_id = row.get("edge_id") or f"{row['u']}_{row['v']}_{row['key']}"
            points.append(((lat, lon), edge_id))

    return points


def get_segments_kdtree(
    segments_path: str = DEFAULT_SEGMENTS_PATH,
) -> KDTree:
    if segments_path not in _CACHED_KDTREES:
        points = load_segmentation_points(segments_path=segments_path)
        _CACHED_KDTREES[segments_path] = KDTree(points)

    return _CACHED_KDTREES[segments_path]


def resolve_street_coords(
    node_data: Any,
    street_geometries: dict[str, tuple[tuple[float, float], ...]] | None = None,
) -> Any:
    "recupera a geometria da rua associada ao dado armazenado no nó da kd-tree"

    if isinstance(node_data, str) and street_geometries is not None:
        return street_geometries.get(node_data)

    if isinstance(node_data, dict):
        if "geometry" in node_data:
            return node_data["geometry"]
        if "edge_id" in node_data and street_geometries is not None:
            return street_geometries.get(node_data["edge_id"])

    return node_data


def project_rider_to_nearest_street(
    rider: Rider,
    kdtree: KDTree,
    street_geometries: dict[str, tuple[tuple[float, float], ...]] | None = None,
    geohash_size: int = 8,
) -> Rider:
    "encontra o ponto de segmentação mais próximo e projeta o entregador na respectiva rua"

    rider_coords = (rider.latitude, rider.longitude)
    nearest_node, _ = kdtree.find_nearest(rider_coords)
    if nearest_node is None:
        return rider

    street_coords = resolve_street_coords(nearest_node.data, street_geometries)
    if street_coords is not None:
        proj_lat, proj_lon = project_point_on_street(rider_coords, street_coords)
    else:
        proj_lat, proj_lon = nearest_node.coords

    rider.latitude = float(proj_lat)
    rider.longitude = float(proj_lon)
    rider.geohash = geohash_encode(rider.latitude, rider.longitude, size=geohash_size)
    return rider


def snap_riders_to_streets(
    riders: Iterable[Rider],
    kdtree: KDTree | None = None,
    street_geometries: dict[str, tuple[tuple[float, float], ...]] | None = None,
    segments_path: str = DEFAULT_SEGMENTS_PATH,
    road_network: Any = None,
    graph_path: str = DEFAULT_GRAPH_PATH,
    geohash_size: int = 8,
) -> list[Rider]:
    riders_list = list(riders)
    if not riders_list:
        return []

    if kdtree is None:
        kdtree = get_segments_kdtree(segments_path=segments_path)

    if street_geometries is None:
        street_geometries = get_street_geometries(
            road_network=road_network,
            graph_path=graph_path,
        )

    for rider in riders_list:
        project_rider_to_nearest_street(
            rider=rider,
            kdtree=kdtree,
            street_geometries=street_geometries,
            geohash_size=geohash_size,
        )

    return riders_list


def generate_riders_data(
    bars: Iterable[Bar],
    num_riders: int,
    std_dev_meters: float = 500.0,
    start_id: int = 1,
    seed: int | None = None,
    kdtree: KDTree | None = None,
    street_geometries: dict[str, tuple[tuple[float, float], ...]] | None = None,
    segments_path: str = DEFAULT_SEGMENTS_PATH,
    road_network: Any = None,
    graph_path: str = DEFAULT_GRAPH_PATH,
) -> list[Rider]:
    """gera entregadores distribuídos homogeneamente entre os bares válidos,
    posicionados conforme distribuição normal em torno de cada estabelecimento
    e projetados na rua do ponto de segmentação mais próximo
    """
    if num_riders <= 0:
        return []

    valid_bars = filter_valid_bars(bars)
    if not valid_bars:
        return []

    rng = np.random.default_rng(seed)
    quotas = calculate_bar_quotas(num_riders, len(valid_bars), rng=rng)

    riders: list[Rider] = []
    current_id = start_id

    for bar, count in zip(valid_bars, quotas):
        if count <= 0:
            continue

        coordinates = sample_normal_coordinates(
            center_lat=bar.latitude,
            center_lon=bar.longitude,
            count=count,
            std_dev_meters=std_dev_meters,
            rng=rng,
        )

        for lat, lon in coordinates:
            rider = build_rider(current_id, lat, lon)
            riders.append(rider)
            current_id += 1

    # corrige a posição de cada entregador projetando eles em suas ruas mais próximas
    snap_riders_to_streets(
        riders=riders,
        kdtree=kdtree,
        street_geometries=street_geometries,
        segments_path=segments_path,
        road_network=road_network,
        graph_path=graph_path,
    )

    return riders


