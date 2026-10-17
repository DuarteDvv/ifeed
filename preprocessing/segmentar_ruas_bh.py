#!/usr/bin/env python3
"""Segmentação das arestas da malha viária de BH em pontos, para permitir que a aresta mais próxima
de um entregador seja buscada de forma heurística com uma KD-tree.

Para cada aresta no mapa, cria um ponto de segmentação no seu ponto médio, dividindo ela em duas arestas.
Se uma das duas arestas for maior que N metros, ela é bipartida novamente, até que todas as arestas tenham
N metros ou menos.
"""

import argparse
import os
import osmnx as ox
import pandas as pd
from shapely.geometry import LineString
from src.geometry.geometry_utilities import split_at_middle

__all__ = [
    "obter_geometria_aresta",
    "split_at_middle",
    "bipartir_segmento",
    "segmentar_aresta",
    "gerar_dataset_pontos_ruas",
]


def obter_geometria_aresta(u, v, edge_data, nodes):
    "retorna a LineString correspondente à geometria da aresta"

    if "geometry" in edge_data and edge_data["geometry"] is not None:
        return edge_data["geometry"]

    u_coords = (nodes[u]["x"], nodes[u]["y"])
    v_coords = (nodes[v]["x"], nodes[v]["y"])
    return LineString([u_coords, v_coords])


def bipartir_segmento(geom, *args):
    "biparte recursivamente um segmento no ponto médio até atingir o comprimento máximo"
    if len(args) == 3:
        comprimento_atual, max_comprimento, pontos = args
    elif len(args) == 5:
        _, _, comprimento_atual, max_comprimento, pontos = args
    else:
        raise TypeError(f"bipartir_segmento esperava 4 ou 6 argumentos, recebeu {len(args) + 1}")

    ponto, geom_esq, geom_dir = split_at_middle(geom)
    pontos.append(ponto)

    comprimento_subaresta = comprimento_atual / 2.0
    if comprimento_subaresta > max_comprimento:
        bipartir_segmento(geom_esq, comprimento_subaresta, max_comprimento, pontos)
        bipartir_segmento(geom_dir, comprimento_subaresta, max_comprimento, pontos)


def segmentar_aresta(geom, comprimento, max_comprimento=50.0):
    "gera pontos de segmentação para uma aresta a partir de bipartição sucessiva"
    pontos = []
    comprimento_valido = max(float(comprimento or 0.0), 0.0)
    bipartir_segmento(geom, comprimento_valido, max_comprimento, pontos)
    return pontos


def gerar_dataset_pontos_ruas(graph, max_comprimento=50.0):
    "gera um dataframe com pontos de segmentação da malha viária e identificadores das ruas"
    nodes = graph.nodes
    registros = []

    for u, v, k, data in graph.edges(keys=True, data=True):
        geom = obter_geometria_aresta(u, v, data, nodes)
        length = float(data.get("length", 0.0))
        osmid = data.get("osmid")
        name = data.get("name")

        pontos_segmentados = segmentar_aresta(geom, length, max_comprimento=max_comprimento)

        for pt in pontos_segmentados:
            registros.append({
                "latitude": pt.y,
                "longitude": pt.x,
                "u": u,
                "v": v,
                "key": k,
                "edge_id": f"{u}_{v}_{k}",
                "osmid": osmid,
                "name": name,
                "original_length": length,
            })

    df = pd.DataFrame(registros)
    return df


def main():
    parser = argparse.ArgumentParser(
        description="gera dataset de pontos médios segmentados da malha viária de BH"
    )
    parser.add_argument(
        "--grafo",
        default="data/malha_viaria_bh.graphml",
        help="caminho do arquivo graphml da malha viária (padrão: data/malha_viaria_bh.graphml)",
    )
    parser.add_argument(
        "--saida",
        default="data/segmentos_ruas_bh.csv.gz",
        help="caminho de saída para salvar o dataset gerado (padrão: data/segmentos_ruas_bh.csv.gz)",
    )
    parser.add_argument(
        "--max-comprimento",
        type=float,
        default=50.0,
        help="comprimento máximo em metros para cada sub-aresta (padrão: 50.0)",
    )

    args = parser.parse_args()

    print(f"Carregando grafo de {args.grafo}...")
    grafo = ox.load_graphml(filepath=args.grafo)
    print(f"Grafo carregado com {grafo.number_of_nodes()} nós e {grafo.number_of_edges()} arestas.")

    print(f"Iniciando segmentação (limite máximo de {args.max_comprimento}m)...")
    df = gerar_dataset_pontos_ruas(grafo, max_comprimento=args.max_comprimento)

    print(f"Total de pontos gerados: {len(df)}")
    print("Amostra dos dados gerados:")
    print(df.head(5))

    os.makedirs(os.path.dirname(args.saida) or ".", exist_ok=True)
    print(f"Salvando dataset em {args.saida}...")
    df.to_csv(args.saida, index=False, compression="gzip" if args.saida.endswith(".gz") else None)
    print(f"Arquivo salvo com sucesso em: {args.saida}")


if __name__ == "__main__":
    main()
