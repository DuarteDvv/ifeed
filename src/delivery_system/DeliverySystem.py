import csv
import gzip
from osmnx import load_graphml

from src.geo_index.radix_tree.RadixTree import RadixTree
from src.models.Rider import Rider
from src.models.Bar import Bar
from src.geo_index.geohash.geohashing import geohash_encode
from src.spatial_search.spatial_search import classify_candidates, osm_distance_and_time, search_candidates


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
    
    def generate_riders(self, num_riders):
        """Gera um número especificado de entregadores com IDs únicos"""
        # TODO DUDU

        pass

    def search_nearby(self, bar_id, radius=1000):
        """Busca entregadores próximos ao bar, com raio informado em metros.

        Retorna None se o bar não existir ou não tiver coordenadas.
        Retorna uma lista, possivelmente vazia, para consultas válidas.
        """
        bar = self.get_bar(bar_id)
        if bar is None or bar.latitude is None or bar.longitude is None:
            return None

        restaurant_location = (bar.latitude, bar.longitude)
        bar_geohash = bar.geohash
        candidate_ids = search_candidates(self.radix_tree, bar_geohash)

        candidates = []
        for candidate_id in candidate_ids:
            rider = self.get_rider(candidate_id)
            candidates.append(rider)

        classified = classify_candidates(candidates, restaurant_location, radius)
        results = osm_distance_and_time(self.road_network, classified, restaurant_location)
        
        return results



    def load_bars(self):
        """carrega os bares de data/bares_final.csv.gz e calcula seus geohashes"""

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

