"""Geração e distribuição espacial de entregadores em torno de bares"""

from typing import Iterable
import numpy as np

from src.geo_index.geohash.geohashing import geohash_encode
from src.models.Bar import Bar
from src.models.Rider import Rider


def filter_valid_bars(bars: Iterable[Bar]) -> list[Bar]:
    """filtra e retorna apenas bares que possuem latitude e longitude definidas"""
    return [
        bar for bar in bars
        if bar.latitude is not None and bar.longitude is not None
    ]


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


METERS_PER_DEGREE = 111_139.0


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

    lats = center_lat + dlat
    lons = center_lon + dlon

    coordinates = []
    for lat, lon in zip(lats, lons):
        clipped_lat = float(max(-90.0, min(90.0, lat)))
        clipped_lon = float(max(-180.0, min(180.0, lon)))
        coordinates.append((clipped_lat, clipped_lon))

    return coordinates


def build_rider(
    rider_id: int,
    latitude: float,
    longitude: float,
    geohash_size: int = 8,
) -> Rider:
    """instancia um Rider com suas coordenadas e geohash calculado"""
    rider_geohash = geohash_encode(latitude, longitude, size=geohash_size)
    return Rider(
        id=rider_id,
        latitude=latitude,
        longitude=longitude,
        geohash=rider_geohash,
    )


def generate_riders_data(
    bars: Iterable[Bar],
    num_riders: int,
    std_dev_meters: float = 500.0,
    start_id: int = 1,
    seed: int | None = None,
) -> list[Rider]:
    """gera entregadores distribuídos homogeneamente entre os bares válidos,
    posicionados conforme distribuição normal em torno de cada estabelecimento
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

    return riders

