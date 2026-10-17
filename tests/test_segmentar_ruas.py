"""Execute na raiz do projeto, com o ambiente ativado: python tests/test_segmentar_ruas.py"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import networkx as nx
import pandas as pd
from shapely.geometry import LineString

from preprocessing.segmentar_ruas_bh import (
    gerar_dataset_pontos_ruas,
    obter_geometria_aresta,
    segmentar_aresta,
)


print("Teste 1 - Arestas curtas (apenas 1 ponto médio)")
# Aresta de 40m: dividida em duas metades de 20m (<= 50m). Deve parar com 1 ponto.
line_40m = LineString([(0, 0), (0, 40)])
pts_40m = segmentar_aresta(line_40m, comprimento=40.0, max_comprimento=50.0)
print("Aresta 40m - quantidade de pontos esperada: 1, obtida:", len(pts_40m))
assert len(pts_40m) == 1, "Deveria ter gerado exatamente 1 ponto"
assert pts_40m[0].x == 0 and pts_40m[0].y == 20, "O ponto gerado deve ser o ponto médio exato (0, 20)"

# Aresta de 80m: dividida em duas metades de 40m (<= 50m). Deve parar com 1 ponto.
line_80m = LineString([(0, 0), (0, 80)])
pts_80m = segmentar_aresta(line_80m, comprimento=80.0, max_comprimento=50.0)
print("Aresta 80m - quantidade de pontos esperada: 1, obtida:", len(pts_80m))
assert len(pts_80m) == 1, "Deveria ter gerado exatamente 1 ponto"
assert pts_80m[0].x == 0 and pts_80m[0].y == 40, "O ponto gerado deve ser o ponto médio exato (0, 40)"


print("\nTeste 2 - Bipartição recursiva com aresta de 120 metros")
# 120m -> metades de 60m (> 50m) -> quartos de 30m (<= 50m).
# Deve gerar 3 pontos: em 25% (30m), 50% (60m) e 75% (90m).
line_120m = LineString([(0, 0), (0, 120)])
pts_120m = segmentar_aresta(line_120m, comprimento=120.0, max_comprimento=50.0)
y_coords_120m = sorted([round(p.y, 2) for p in pts_120m])
print("Aresta 120m - quantidade de pontos esperada: 3, obtida:", len(pts_120m))
print("Coordenadas Y esperadas: [30.0, 60.0, 90.0], obtidas:", y_coords_120m)
assert len(pts_120m) == 3, "Deveria ter gerado exatamente 3 pontos"
assert y_coords_120m == [30.0, 60.0, 90.0], "Pontos de bipartição incorretos"


print("\nTeste 3 - Bipartição recursiva com aresta longa de 240 metros")
# 240m -> metades de 120m -> quartos de 60m -> oitavos de 30m (<= 50m).
# Total de pontos: 2^3 - 1 = 7 pontos.
line_240m = LineString([(0, 0), (0, 240)])
pts_240m = segmentar_aresta(line_240m, comprimento=240.0, max_comprimento=50.0)
y_coords_240m = sorted([round(p.y, 2) for p in pts_240m])
print("Aresta 240m - quantidade de pontos esperada: 7, obtida:", len(pts_240m))
print("Coordenadas Y esperadas (múltiplos de 30):", [30.0 * i for i in range(1, 8)])
print("Coordenadas Y obtidas:", y_coords_240m)
assert len(pts_240m) == 7, "Deveria ter gerado 7 pontos"
assert y_coords_240m == [30.0 * i for i in range(1, 8)], "Pontos de bipartição em 240m incorretos"


print("\nTeste 4 - Preservação da curvatura da via vs linha reta")
# Rota em L: (0, 0) -> (0, 50) -> (50, 50). Comprimento total = 100m.
# Se cortasse em linha reta de (0, 0) a (50, 50), o ponto médio seria (25, 25).
# Como segue a curva, o ponto médio (50%) está exatamente na quina (0, 50).
curva_l = LineString([(0, 0), (0, 50), (50, 50)])
pts_curva = segmentar_aresta(curva_l, comprimento=100.0, max_comprimento=50.0)
assert len(pts_curva) == 1, "Deveria ter gerado 1 ponto médio"
ponto_meio = pts_curva[0]
print("Ponto médio da curva em L obtido:", (ponto_meio.x, ponto_meio.y))
print("Ponto esperado se seguisse a curva: (0.0, 50.0)")
assert round(ponto_meio.x, 2) == 0.0 and round(ponto_meio.y, 2) == 50.0, "O ponto não seguiu a geometria da curva!"


print("\nTeste 5 - Geração do DataFrame em grafo simulado")
G = nx.MultiDiGraph()
G.add_node(1, x=-43.93, y=-19.92)
G.add_node(2, x=-43.93, y=-19.91)  # reta de ~1100m
G.add_node(3, x=-43.94, y=-19.91)

# Aresta 1: curta (40m) sem geometry explícita
G.add_edge(1, 3, key=0, length=40.0, osmid=1001, name="Rua Curta")
# Aresta 2: média (120m) sem geometry explícita
G.add_edge(3, 2, key=0, length=120.0, osmid=1002, name="Rua Média")
# Aresta 3: curva com 3 vértices
geom_curva = LineString([(-43.93, -19.92), (-43.935, -19.915), (-43.93, -19.91)])
G.add_edge(1, 2, key=0, length=120.0, geometry=geom_curva, osmid=1003, name="Avenida Curva")

df = gerar_dataset_pontos_ruas(G, max_comprimento=50.0)
print("Shape do DataFrame:", df.shape)
print("Colunas presentes:", list(df.columns))

# Validações das colunas
colunas_esperadas = ["latitude", "longitude", "u", "v", "key", "edge_id", "osmid", "name", "original_length"]
assert list(df.columns) == colunas_esperadas, "Colunas do DataFrame não correspondem ao esperado"

# Contagem esperada: 1 ponto (aresta curta) + 3 pontos (aresta média) + 3 pontos (aresta curva) = 7 pontos
assert len(df) == 7, f"Esperado 7 pontos no grafo simulado, obtido {len(df)}"
assert set(df["name"]) == {"Rua Curta", "Rua Média", "Avenida Curva"}, "Nomes das ruas incorretos"
assert df["latitude"].notna().all() and df["longitude"].notna().all(), "Coordenadas com valores nulos"


print("\nTeste 6 - Validação do arquivo real salvo (data/pontos_ruas_bh.csv.gz)")
arquivo_saida = "data/pontos_ruas_bh.csv.gz"
if os.path.exists(arquivo_saida):
    df_real = pd.read_csv(arquivo_saida, compression="gzip", nrows=1000)
    print(f"Arquivo {arquivo_saida} verificado!")
    print(f"Amostra de 1.000 linhas carregada com sucesso.")
    print("Média Latitude BH:", round(df_real["latitude"].mean(), 4), "(esperado próximo a -19.9)")
    print("Média Longitude BH:", round(df_real["longitude"].mean(), 4), "(esperado próximo a -43.9)")
    assert (-20.1 <= df_real["latitude"].mean() <= -19.7), "Latitude média fora dos limites de BH"
    assert (-44.1 <= df_real["longitude"].mean() <= -43.8), "Longitude média fora dos limites de BH"

print("\nTodos os testes de segmentar_ruas_bh passaram com sucesso!")

