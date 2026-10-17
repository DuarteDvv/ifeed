"""testes da kdtree e kd_tree_node."""

import os
import sys
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.generation.kd_tree.KD_Tree import KDTree, squared_distance
from src.generation.kd_tree.Node import KDTreeNode


print("teste 1 - kdtree vazia")
tree_empty = KDTree([])
assert tree_empty.root is None
node, dist = tree_empty.find_nearest((1.0, 2.0))
assert node is None and dist == float("inf")
assert tree_empty.find_k_nearest((1.0, 2.0), k=3) == []

print("\nteste 2 - kdtree com pontos 2d clássicos")
# pontos clássicos de kdtree
pts = [(2, 3), (5, 4), (9, 6), (4, 7), (8, 1), (7, 2)]
tree = KDTree(pts)
assert tree.root is not None
assert tree.root.coords in pts

print("\nteste 3 - busca exata e vizinho mais próximo")
nearest_node, dist = tree.find_nearest((2, 3))
assert nearest_node.coords == (2, 3)
assert dist == 0.0

# consulta próxima a (9, 2)
nearest_node, dist = tree.find_nearest((9, 2))
# (8, 1) dist_sq = (9-8)^2 + (2-1)^2 = 2
# (7, 2) dist_sq = (9-7)^2 + (2-2)^2 = 4
assert nearest_node.coords == (8, 1)
assert math.isclose(dist, math.sqrt(2))

print("\nteste 4 - validação contra força bruta (100 pontos aleatórios)")
import numpy as np
rng = np.random.default_rng(123)
random_pts = [tuple(p) for p in rng.uniform(-100, 100, size=(100, 2))]
tree_rand = KDTree(random_pts)

for _ in range(20):
    query = tuple(rng.uniform(-100, 100, size=2))
    # força bruta
    bf_node = min(random_pts, key=lambda p: squared_distance(p, query))
    bf_dist = math.sqrt(squared_distance(bf_node, query))
    
    kd_node, kd_dist = tree_rand.find_nearest(query)
    assert math.isclose(kd_dist, bf_dist, rel_tol=1e-9), f"divergência: kd={kd_dist}, bf={bf_dist}"

print("\nteste 5 - k vizinhos mais próximos")
query = (0.0, 0.0)
k_results = tree_rand.find_k_nearest(query, k=5)
assert len(k_results) == 5

# confere ordenação crescente de distâncias
dists = [d for _, d in k_results]
assert dists == sorted(dists)

# compara com força bruta
bf_sorted = sorted(random_pts, key=lambda p: squared_distance(p, query))[:5]
bf_dists = [math.sqrt(squared_distance(p, query)) for p in bf_sorted]
for i in range(5):
    assert math.isclose(dists[i], bf_dists[i], rel_tol=1e-9)

print("\nteste 6 - dados associados aos pontos (ex: arestas / ruas)")
street_points = [
    ((-19.920, -43.940), {"street_name": "av. afonso pena", "id": 101}),
    ((-19.925, -43.945), {"street_name": "av. amazonas", "id": 102}),
    ((-19.850, -43.960), {"street_name": "av. antonio carlos", "id": 103}),
]
tree_streets = KDTree(street_points)
target_rider = (-19.921, -43.941)
nearest_street_node, street_dist = tree_streets.find_nearest(target_rider)
assert nearest_street_node.data["street_name"] == "av. afonso pena"
assert nearest_street_node.data["id"] == 101

print("\nteste 7 - inserção dinâmica")
tree_insert = KDTree()
tree_insert.insert((10, 20), data="ponto a")
tree_insert.insert((30, 40), data="ponto b")
node_found, _ = tree_insert.find_nearest((11, 21))
assert node_found.data == "ponto a"

print("\ntodos os testes da kdtree passaram com sucesso!")

