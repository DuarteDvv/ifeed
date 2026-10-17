"""Testes unitários para o módulo src/geometry/geometry_utilities.py.
Execute na raiz do projeto: python tests/test_geometry_utilities.py
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from shapely.geometry import LineString

from src.geometry.geometry_utilities import (
    classify_candidates,
    haversine_distance,
    hypot,
    median_geometric,
    split_at_middle,
    split_points_by_median,
    squared_distance,
)
from src.models.Rider import Rider


print("Teste 1 - split_at_middle")
curva_l = LineString([(0, 0), (0, 50), (50, 50)])
ponto, esq, dir = split_at_middle(curva_l)
assert round(ponto.x, 2) == 0.0 and round(ponto.y, 2) == 50.0
assert list(esq.coords) == [(0.0, 0.0), (0.0, 50.0)]
assert list(dir.coords) == [(0.0, 50.0), (50.0, 50.0)]
print("OK: divisão e ponto médio de curva em L")


print("\nTeste 2 - squared_distance")
d2 = squared_distance((1.0, 2.0), (4.0, 6.0))
# (4-1)^2 + (6-2)^2 = 3^2 + 4^2 = 25
assert d2 == 25.0
print(f"OK: squared_distance obtido {d2}")


print("\nTeste 3 - haversine_distance")
h_dist = haversine_distance(0, 0, 0, 1)
assert round(h_dist, 2) == 111194.93
print(f"OK: haversine_distance obtido {round(h_dist, 2)}")


print("\nTeste 4 - classify_candidates")
riders = [Rider(1, -19.921, -43.94), Rider(2, -19.923, -43.94)]
classified = classify_candidates(riders, (-19.92, -43.94), radius=200)
assert len(classified) == 2
assert classified[0]["within_range"] is True
assert classified[1]["within_range"] is False
print("OK: classify_candidates com Rider objects")


print("\nTeste 5 - median_geometric (Weiszfeld)")
# Ponto médio simétrico de 4 cantos de um quadrado deve ser o centro (0, 0)
pts_square = [(-10, -10), (10, -10), (10, 10), (-10, 10)]
med = median_geometric(pts_square)
assert np.allclose(med, [0.0, 0.0], atol=1e-5)
print(f"OK: median_geometric obtida {med}")


print("\nTeste 6 - split_points_by_median")
pts = [(2, 3), (5, 4), (9, 6), (4, 7), (8, 1), (7, 2)]
# Eixo X (axis=0): ordenados por X são [2, 4, 5, 7, 8, 9]. Mediana (len=6, mid=3) é 7 -> (7, 2)
left_p, med_item, right_p = split_points_by_median(pts, axis=0)
assert med_item == (7, 2)
assert len(left_p) == 3
assert len(right_p) == 2
print("OK: split_points_by_median particionado corretamente")


print("\nTeste 7 - hypot")
assert math.isclose(hypot(3.0, 4.0), 5.0)
assert math.isclose(hypot(0.0, 0.0), 0.0)
assert math.isclose(hypot(-3.0, -4.0), 5.0)
print("OK: hypot calcula hipotenusa corretamente")

print("\nTodos os testes de geometry_utilities passaram com sucesso!")
