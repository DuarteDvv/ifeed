"""Execute na raiz do projeto, com o ambiente ativado: python3 tests/test_spatial_search.py"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import networkx as nx

from src.geo_index.radix_tree.RadixTree import RadixTree
from src.models.Rider import Rider
from src.spatial_search.spatial_search import (
    classify_candidates,
    haversine_distance,
    osm_distance_and_time,
    search_candidates,
)


print("Teste 1 - Distância de Haversine em metros")
print("Entrada: haversine_distance(0, 0, 0, 1)")
print("Saída esperada: 111194.93")
print("Saída obtida:", round(haversine_distance(0, 0, 0, 1), 2))

print("\nTeste 2 - Candidatos na célula do bar e nas vizinhas")
tree = RadixTree()
tree.insert("7h2ybb5z", 101)
tree.insert("7h2yb9ab", 102)
tree.insert("7h2xpesh", 103)
print("Entrada: chaves 7h2ybb5z (101), 7h2yb9ab (102), 7h2xpesh (103)")
print("Busca: search_candidates(tree, '7h2ybb5z')")
print("Saída esperada:", [101, 102])
print("Saída obtida:", search_candidates(tree, "7h2ybb5z"))

print("\nTeste 3 - Classificação dentro e fora do raio")
riders = [Rider(101, -19.921, -43.94), Rider(102, -19.923, -43.94)]
print("Entrada: bar=(-19.92, -43.94), raio=200 metros")
print("Entregadores: 101=(-19.921, -43.94), 102=(-19.923, -43.94)")
expected = [
    {"id": 101, "latitude": -19.921, "longitude": -43.94, "distance": 111.19, "within_range": True},
    {"id": 102, "latitude": -19.923, "longitude": -43.94, "distance": 333.58, "within_range": False},
]
print("Saída esperada:", expected)
print("Saída obtida:", classify_candidates(riders, (-19.92, -43.94), 200))

print("\nTeste 4 - Distância e tempo da rota mais rápida")
graph = nx.MultiDiGraph(crs="EPSG:4326")
graph.add_node(0, y=-19.92, x=-43.94)  # bar
graph.add_node(1, y=-19.921, x=-43.94)  # entregador
graph.add_node(2, y=-19.9205, x=-43.94)  # ponto intermediário
graph.add_edge(1, 0, length=300.0, travel_time=120.0)
graph.add_edge(1, 2, length=400.0, travel_time=20.0)
graph.add_edge(2, 0, length=800.0, travel_time=30.0)
candidates = [
    {"id": 101, "latitude": -19.921, "longitude": -43.94, "distance": 111.19, "within_range": True},
    {"id": 102, "latitude": -19.9205, "longitude": -43.94, "distance": 55.6, "within_range": True},
]
print("Entrada: entregadores 101 no nó 1 e 102 no nó 2; bar no nó 0")
print("Rotas: 1 -> 0 = 300 m / 120 s; 1 -> 2 -> 0 = 1200 m / 50 s")
expected = [
    {"id": 101, "latitude": -19.921, "longitude": -43.94, "distance": 111.19,
     "within_range": True, "road_distance": 1200.0, "estimated_time": 0.83},
    {"id": 102, "latitude": -19.9205, "longitude": -43.94, "distance": 55.6,
     "within_range": True, "road_distance": 800.0, "estimated_time": 0.5},
]
print("Saída esperada:", expected)
print("Saída obtida:", osm_distance_and_time(graph, candidates, (-19.92, -43.94)))

print("\nTeste 5 - Sem rota do entregador até o bar")
graph = nx.MultiDiGraph(crs="EPSG:4326")
graph.add_node(0, y=-19.92, x=-43.94)
graph.add_node(1, y=-19.921, x=-43.94)
graph.add_edge(0, 1, length=500.0, travel_time=60.0)
candidates = [
    {"id": 101, "latitude": -19.921, "longitude": -43.94, "distance": 111.19, "within_range": True},
]
print("Entrada: entregador no nó 1, bar no nó 0; existe apenas a rua 0 -> 1")
expected = [
    {"id": 101, "latitude": -19.921, "longitude": -43.94, "distance": 111.19,
     "within_range": True, "road_distance": None, "estimated_time": None},
]
print("Saída esperada:", expected)
print("Saída obtida:", osm_distance_and_time(graph, candidates, (-19.92, -43.94)))
