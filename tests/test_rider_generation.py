"""Testes unitários rápidos para o módulo src/generation/rider_generation.py.
Execute na raiz do projeto: python tests/test_rider_generation.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from src.generation.kd_tree.KD_Tree import KDTree
from src.generation.rider_generation import (
    build_rider,
    calculate_bar_quotas,
    filter_valid_bars,
    generate_riders_data,
    get_segments_kdtree,
    get_street_geometries,
    project_rider_to_nearest_street,
    sample_normal_coordinates,
)
from src.geometry.geometry_utilities import project_point_on_street, squared_distance
from src.models.Bar import Bar


def make_bar(bar_id, lat=None, lon=None):
    return Bar(
        id=bar_id,
        nome=f"Bar {bar_id}",
        nome_fantasia=f"Fantasia {bar_id}",
        endereco="Rua Teste",
        bairro="Centro",
        latitude=lat,
        longitude=lon,
    )


print("Teste 1 - filter_valid_bars")
bars = [
    make_bar(1, -19.92, -43.94),
    make_bar(2, None, None),
    make_bar(3, -19.93, None),
    make_bar(4, -19.91, -43.93),
]
valid = filter_valid_bars(bars)
print("Entrada: 4 bares (2 válidos, 2 sem coordenadas completas)")
print("IDs válidos esperados: [1, 4]")
print("IDs válidos obtidos:", [b.id for b in valid])
assert [b.id for b in valid] == [1, 4], "Erro no Teste 1"

print("\nTeste 2 - calculate_bar_quotas")
rng = np.random.default_rng(42)
quotas_1 = calculate_bar_quotas(num_riders=10, num_bars=3, rng=rng)
quotas_2 = calculate_bar_quotas(num_riders=2, num_bars=5, rng=rng)
quotas_3 = calculate_bar_quotas(num_riders=0, num_bars=4, rng=rng)
print("Quotas 10 entregadores em 3 bares:", quotas_1, "Soma:", sum(quotas_1))
print("Quotas 2 entregadores em 5 bares:", quotas_2, "Soma:", sum(quotas_2))
print("Quotas 0 entregadores em 4 bares:", quotas_3, "Soma:", sum(quotas_3))
assert sorted(quotas_1) == [3, 3, 4] and sum(quotas_1) == 10, "Erro quotas 1"
assert sorted(quotas_2) == [0, 0, 0, 1, 1] and sum(quotas_2) == 2, "Erro quotas 2"
assert quotas_3 == [0, 0, 0, 0] and sum(quotas_3) == 0, "Erro quotas 3"

# Teste de aleatoriedade da seleção do remainder sem reposição
distinct_selections = set()
for s in range(50):
    q = calculate_bar_quotas(num_riders=1, num_bars=10, rng=np.random.default_rng(s))
    selected_bar = q.index(1)
    distinct_selections.add(selected_bar)
print(f"Bares contemplados aleatoriamente em 50 execuções (de 10 bares): {len(distinct_selections)}")
assert len(distinct_selections) > 1, "A seleção do remainder não foi aleatória"

print("\nTeste 3 - sample_normal_coordinates")
rng = np.random.default_rng(42)
coords = sample_normal_coordinates(
    center_lat=-19.92,
    center_lon=-43.94,
    count=1000,
    std_dev_meters=500.0,
    rng=rng,
)
print("Quantidade de coordenadas geradas:", len(coords))
lats = [c[0] for c in coords]
lons = [c[1] for c in coords]
mean_lat = np.mean(lats)
mean_lon = np.mean(lons)
print(f"Média Lat: {mean_lat:.5f} (esperado próximo a -19.92000)")
print(f"Média Lon: {mean_lon:.5f} (esperado próximo a -43.94000)")
assert len(coords) == 1000, "Erro no tamanho de coordenadas"
assert abs(mean_lat - (-19.92)) < 0.001, "Média de latitude distante do centro"
assert abs(mean_lon - (-43.94)) < 0.001, "Média de longitude distante do centro"

print("\nTeste 4 - build_rider")
rider = build_rider(rider_id=42, latitude=-19.921, longitude=-43.941)
print(f"Rider construído: id={rider.id}, lat={rider.latitude}, lon={rider.longitude}, geohash={rider.geohash}")
assert rider.id == 42, "ID incorreto"
assert rider.geohash is not None and len(rider.geohash) == 8, "Geohash inválido"

print("\nTeste 5 - project_rider_to_nearest_street em rua sintética")
# rua horizontal em lat = -19.920, indo de lon = -43.950 até lon = -43.930, com ponto médio em (-19.920, -43.940)
mock_kdtree = KDTree([((-19.920, -43.940), "rua_1")])
mock_geometries = {"rua_1": ((-19.920, -43.950), (-19.920, -43.930))}
rider_fora_da_rua = build_rider(rider_id=1, latitude=-19.918, longitude=-43.943)
project_rider_to_nearest_street(rider_fora_da_rua, mock_kdtree, mock_geometries)
print(f"Posição após projeção: ({rider_fora_da_rua.latitude}, {rider_fora_da_rua.longitude})")
assert np.isclose(rider_fora_da_rua.latitude, -19.920), "Latitude deveria ter sido projetada para -19.920"
assert np.isclose(rider_fora_da_rua.longitude, -43.943), "Longitude deveria ser preservada na projeção ortogonal"

print("\nTeste 6 - generate_riders_data com projeção nas ruas reais de BH")
test_bars = [
    make_bar(10, -19.92, -43.94),
    make_bar(20, -19.85, -43.96),
    make_bar(30, None, None),
]
riders = generate_riders_data(
    bars=test_bars,
    num_riders=5,
    std_dev_meters=500.0,
    start_id=100,
    seed=123,
)
print("Entregadores gerados:", len(riders))
print("IDs gerados:", [r.id for r in riders])
assert len(riders) == 5, "Total de entregadores gerados incorreto"
assert [r.id for r in riders] == [100, 101, 102, 103, 104], "IDs não sequenciais"

kdtree_bh = get_segments_kdtree()
geometries_bh = get_street_geometries()
for r in riders:
    assert r.geohash is not None and len(r.geohash) == 8, "Geohash ausente"
    # verifica se o entregador está exatamente sobre uma rua próxima da malha viária
    nearest_candidates = kdtree_bh.find_k_nearest((r.latitude, r.longitude), k=10)
    min_dist_sq = min(
        squared_distance(
            (r.latitude, r.longitude),
            project_point_on_street((r.latitude, r.longitude), geometries_bh[node.data]),
        )
        for node, _ in nearest_candidates
    )
    assert min_dist_sq < 1e-18, f"Entregador {r.id} não está sobre uma rua (min_dist_sq={min_dist_sq})"

print("OK: todos os entregadores gerados estão projetados sobre ruas reais de BH")
print("\nTodos os testes unitários de rider_generation passaram com sucesso!")

