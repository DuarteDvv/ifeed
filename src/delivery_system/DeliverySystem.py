import csv
import gzip
from osmnx import load_graphml

from src.generation.rider_generation import (
    filter_candidates_by_radius,
    generate_riders_data,
)
from src.geo_index.radix_tree.RadixTree import RadixTree
from src.models.Rider import Rider
from src.models.Bar import Bar
from src.geo_index.geohash.geohashing import geohash_encode
from src.spatial_search.spatial_search import (
    classify_candidates_by_distance,
    osm_distance_and_time,
    search_candidates,
)


class DeliverySystem:
    def __init__(self):
        self.radix_tree = RadixTree()
        self.riders = {}
        self.bars = self.load_bars()
        self.road_network = load_graphml(filepath="data/malha_viaria_bh.graphml")

    def get_rider(self, rider_id):
        return self.riders.get(rider_id)

    def get_bar(self, bar_id):
        return self.bars.get(bar_id)
    
    def generate_riders(
        self,
        num_riders: int,
        std_dev_meters: float = 500.0,
        seed: int | None = None,
        clear_existing: bool = False,
    ) -> list[Rider]:
        """gera entregadores distribuídos homogeneamente entre os bares disponíveis,
        posicionados conforme distribuição Normal em metros em torno de cada bar
        """
        if num_riders <= 0:
            return []

        if clear_existing:
            self.riders = {}
            self.radix_tree = RadixTree()
            start_id = 1
        else:
            start_id = max(self.riders.keys(), default=0) + 1

        generated_riders = generate_riders_data(
            bars=self.bars.values(),
            num_riders=num_riders,
            std_dev_meters=std_dev_meters,
            start_id=start_id,
            seed=seed,
            road_network=getattr(self, "road_network", None),
        )

        for rider in generated_riders:
            self.riders[rider.id] = rider
            self.radix_tree.insert(rider.geohash, rider.id)

        return generated_riders

    def search_nearby(
        self,
        bar_id: int,
        radius: float | None = None,
        radius_km: float | None = None,
        only_within_range: bool = False,
    ):
        bar = self.get_bar(bar_id)
        if bar is None or bar.latitude is None or bar.longitude is None:
            return None

        if radius_km is not None:
            radius_meters = float(radius_km) * 1000.0
        elif radius is not None:
            radius_meters = float(radius)
        else:
            radius_meters = 1000.0

        restaurant_location = (bar.latitude, bar.longitude)
        bar_geohash = bar.geohash
        candidate_ids = search_candidates(self.radix_tree, bar_geohash)

        candidates = []
        for candidate_id in candidate_ids:
            rider = self.get_rider(candidate_id)
            if rider is not None:
                candidates.append(rider)

        classified = classify_candidates_by_distance(candidates, restaurant_location, radius_meters)
        if only_within_range:
            classified = filter_candidates_by_radius(classified)

        results = osm_distance_and_time(self.road_network, classified, restaurant_location)
        
        return results



    def load_bars(self):
        "carrega os bares e calcula seus geohashes"

        csv_path = "data/bares_final.csv.gz"

        bars = {}

        with gzip.open(csv_path, mode="rt", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.DictReader(csv_file)

            for row in reader:
                bar_id = int(row["_id"])
                latitude_text = (row.get("latitude") or "").strip()
                longitude_text = (row.get("longitude") or "").strip()

                if latitude_text and longitude_text:
                    latitude = float(latitude_text)
                    longitude = float(longitude_text)
                else:
                    latitude = None
                    longitude = None

                address_parts = (
                    row.get("DESC_LOGRADOURO"),
                    row.get("NOME_LOGRADOURO"),
                    row.get("NUMERO_IMOVEL"),
                    row.get("COMPLEMENTO"),
                )
                address = " ".join(
                    part.strip() for part in address_parts if part and part.strip()
                )

                bar = Bar(
                    id=bar_id,
                    nome=(row.get("NOME") or "").strip(),
                    nome_fantasia=(row.get("NOME_FANTASIA") or "").strip(),
                    endereco=address,
                    bairro=(row.get("NOME_BAIRRO") or "").strip(),
                    latitude=latitude,
                    longitude=longitude,
                )
                if latitude is not None and longitude is not None:
                    bar.geohash = geohash_encode(latitude, longitude, size=8)

                bars[bar.id] = bar

        return bars

