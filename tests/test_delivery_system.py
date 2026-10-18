"""Execute na raiz, com o ambiente ativado: python3 tests/test_delivery_system.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.delivery_system.DeliverySystem import DeliverySystem
from src.geo_index.geohash.geohashing import geohash_encode
from src.models.Rider import Rider


print("Teste 1 - Carregamento do CSV e do grafo reais")
print("Entrada: DeliverySystem(), usando os arquivos de data/")
system = DeliverySystem()
print("Saída esperada:", {"bares": 20859, "nos": 32255, "arestas": 82877})
print("Saída obtida:", {
    "bares": len(system.bars),
    "nos": system.road_network.number_of_nodes(),
    "arestas": system.road_network.number_of_edges(),
})

print("\nTeste 2 - Bar real com coordenadas, mas sem entregadores cadastrados")
bar = system.get_bar(12)
print("Entrada: search_nearby(12, radius=200)")
print("Bar:", bar.nome, "Coordenadas:", (bar.latitude, bar.longitude))
print("Saída esperada:", [])
print("Saída obtida:", system.search_nearby(12, radius=200))

print("\nTeste 3 - Estabelecimento real sem coordenadas")
bar_without_coordinates = system.get_bar(3866)
print("Entrada: search_nearby(3866, radius=200)")
print("Bar:", bar_without_coordinates.nome)
print("Coordenadas:", (bar_without_coordinates.latitude, bar_without_coordinates.longitude))
print("Saída esperada:", None)
print("Saída obtida:", system.search_nearby(3866, radius=200))

print("\nTeste 4 - ID de estabelecimento inexistente")
print("Entrada: search_nearby(-1, radius=200)")
print("Saída esperada:", None)
print("Saída obtida:", system.search_nearby(-1, radius=200))

print("\nTeste 5 - Entregadores artificiais em nós do grafo real")
print("Entrada: bar 12, raio de 200 metros")
print("Entregador 101: próximo; 102: fora do raio; 103: distante da região de busca")
rider_nodes = [(101, 101043556), (102, 4988365536), (103, 32448892)]

for rider_id, node_id in rider_nodes:
    node = system.road_network.nodes[node_id]
    rider = Rider(rider_id, node["y"], node["x"])
    rider.geohash = geohash_encode(rider.latitude, rider.longitude, size=8)
    system.riders[rider.id] = rider
    system.radix_tree.insert(rider.geohash, rider.id)
    print(f"Entregador {rider.id}: nó {node_id}, coordenadas {(rider.latitude, rider.longitude)}")

expected = [
    {
        "id": 101,
        "latitude": -19.8441013,
        "longitude": -43.9618594,
        "distance": 104.59,
        "within_range": True,
        "road_distance": 575.15,
        "estimated_time": 0.88,
    },
    {
        "id": 102,
        "latitude": -19.8407988,
        "longitude": -43.963161,
        "distance": 321.13,
        "within_range": False,
        "road_distance": 577.16,
        "estimated_time": 0.89,
    },
]
print("Saída esperada (ordenada por ID):", expected)
results = system.search_nearby(12, radius=200)
print("Saída obtida (ordenada por ID):", sorted(results, key=lambda result: result["id"]))

print("\nTeste 6 - generate_riders com distribuição normal em torno dos bares")
generated = system.generate_riders(num_riders=1000, std_dev_meters=300.0, seed=123, clear_existing=True)
print("Quantidade gerada:", len(generated))
print("Quantidade no sistema (riders):", len(system.riders))
print("IDs únicos e no intervalo 1..1000:", set(system.riders.keys()) == set(range(1, 1001)))
print("Exemplo de entregador gerado:", {
    "id": generated[0].id,
    "latitude": round(generated[0].latitude, 6),
    "longitude": round(generated[0].longitude, 6),
    "geohash": generated[0].geohash,
})
nearby_generated = system.search_nearby(12, radius=1000)
print(f"Entregadores próximos ao bar 12 (raio 1000m): {len(nearby_generated)}")

print("\nTeste 7 - search_nearby com only_within_range=True (filtrando apenas dentro do raio)")
nearby_filtered = system.search_nearby(12, radius=1000, only_within_range=True)
print(f"Entregadores dentro do raio de 1000m: {len(nearby_filtered)}")
assert all(r["within_range"] is True for r in nearby_filtered), "Todos os entregadores retornados devem ter within_range=True"
assert all(r["distance"] <= 1000.0 for r in nearby_filtered), "Nenhum entregador deve estar a mais de 1000m"

# teste com radius_km=1.0
nearby_filtered_km = system.search_nearby(12, radius_km=1.0, only_within_range=True)
assert len(nearby_filtered_km) == len(nearby_filtered), "radius_km=1.0 deve equivaler a radius=1000"
print("OK: search_nearby filtra perfeitamente candidatos dentro do raio!")


