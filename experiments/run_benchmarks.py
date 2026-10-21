"""script de benchmark experimental para avaliar geracao de entregadores e busca espacial"""

import csv
import gc
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import osmnx as ox

# adiciona o diretorio raiz ao sys.path para permitir importacoes diretas
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.delivery_system.DeliverySystem import DeliverySystem
from src.generation.kd_tree.KD_Tree import KDTree
from src.generation.rider_generation import (
    build_rider,
    build_street_geometries_map,
    calculate_bar_quotas,
    filter_candidates_by_radius,
    filter_valid_bars,
    load_segmentation_points,
    resolve_street_coords,
    sample_normal_coordinates,
)
from src.geo_index.geohash.geohashing import geohash_encode
from src.geo_index.radix_tree.RadixTree import RadixTree
from src.geometry.geometry_utilities import (
    classify_candidates_by_distance,
    project_point_on_street,
)
from src.spatial_search.spatial_search import (
    search_candidates,
    select_geohash_prefix_size,
)
from src.webpage.map_data import create_map_url
from src.webpage.riders import build_rider_feature

RIDER_COUNTS = [100, 500, 1000, 2500, 5000, 10000, 25000, 50000]
SEARCH_RADII_KM = [0.5, 1.0, 2.0]
GENERATION_REPEATS = 5
SEARCH_REPEATS = 3
RESULTS_DIR = ROOT_DIR / "experiments" / "results"


def measure_initialization() -> tuple[DeliverySystem, KDTree, dict[str, Any], dict[str, float]]:
    """mede o tempo de inicializacao de cada estrutura de dados base do sistema"""
    print("=== 0. Medindo Inicializacao das Estruturas Base ===")
    gc.collect()

    t0 = time.perf_counter_ns()
    system = DeliverySystem.__new__(DeliverySystem)
    system.riders = {}
    system.radix_tree = RadixTree()
    system.bars = system.load_bars()
    t1 = time.perf_counter_ns()
    t_load_bars_ms = (t1 - t0) / 1e6
    print(f"  - Carregamento de bares + Geohash ({len(system.bars)} bares): {t_load_bars_ms:.2f} ms")

    t2 = time.perf_counter_ns()
    system.road_network = ox.load_graphml(filepath="data/malha_viaria_bh.graphml")
    t3 = time.perf_counter_ns()
    t_load_graph_ms = (t3 - t2) / 1e6
    print(
        f"  - Carregamento da malha viaria ({len(system.road_network.nodes)} nos, "
        f"{len(system.road_network.edges)} arestas): {t_load_graph_ms:.2f} ms"
    )

    t4 = time.perf_counter_ns()
    seg_points = load_segmentation_points("data/segmentos_ruas_bh.csv.gz")
    t5 = time.perf_counter_ns()
    t_load_seg_ms = (t5 - t4) / 1e6
    print(f"  - Leitura dos pontos de segmentacao ({len(seg_points)} pontos): {t_load_seg_ms:.2f} ms")

    t6 = time.perf_counter_ns()
    kdtree = KDTree(seg_points)
    t7 = time.perf_counter_ns()
    t_build_kdtree_ms = (t7 - t6) / 1e6
    print(f"  - Construcao da KD-Tree 2D: {t_build_kdtree_ms:.2f} ms")

    t8 = time.perf_counter_ns()
    street_geometries = build_street_geometries_map(system.road_network)
    t9 = time.perf_counter_ns()
    t_build_geoms_ms = (t9 - t8) / 1e6
    print(f"  - Indexacao das geometrias das ruas ({len(street_geometries)} arestas): {t_build_geoms_ms:.2f} ms")

    init_metrics = {
        "num_bars": len(system.bars),
        "num_nodes": len(system.road_network.nodes),
        "num_edges": len(system.road_network.edges),
        "num_seg_points": len(seg_points),
        "t_load_bars_ms": round(t_load_bars_ms, 3),
        "t_load_graph_ms": round(t_load_graph_ms, 3),
        "t_load_seg_points_ms": round(t_load_seg_ms, 3),
        "t_build_kdtree_ms": round(t_build_kdtree_ms, 3),
        "t_build_street_geoms_ms": round(t_build_geoms_ms, 3),
        "t_total_init_ms": round(
            t_load_bars_ms + t_load_graph_ms + t_load_seg_ms + t_build_kdtree_ms + t_build_geoms_ms, 3
        ),
    }
    return system, kdtree, street_geometries, init_metrics


def run_single_generation_benchmark(
    valid_bars: list[Any],
    num_riders: int,
    kdtree: KDTree,
    street_geometries: dict[str, Any],
    seed: int,
    std_dev_meters: float = 500.0,
) -> tuple[dict[str, float], dict[int, Any], RadixTree]:
    """executa e cronometra detalhadamente cada sub-tarefa da geracao e renderizacao de entregadores"""
    gc.collect()
    gc.disable()
    try:
        # sub-tarefa 1.1: calculo de quotas, amostragem normal e instanciacao inicial
        t0 = time.perf_counter_ns()
        rng = np.random.default_rng(seed)
        quotas = calculate_bar_quotas(num_riders, len(valid_bars), rng=rng)
        riders = []
        current_id = 1
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
                rider = build_rider(current_id, lat, lon, geohash_size=8)
                riders.append(rider)
                current_id += 1
        t1 = time.perf_counter_ns()
        t_sampling_ms = (t1 - t0) / 1e6

        # sub-tarefa 1.2a: busca do ponto de segmentacao mais proximo na kd-tree
        t2 = time.perf_counter_ns()
        nearest_nodes = [kdtree.nearest((r.latitude, r.longitude)) for r in riders]
        t3 = time.perf_counter_ns()
        t_kdtree_nearest_ms = (t3 - t2) / 1e6

        # sub-tarefa 1.2b: projecao ortogonal no segmento da rua e recalculo do geohash
        t4 = time.perf_counter_ns()
        for rider, nearest_node in zip(riders, nearest_nodes):
            if nearest_node is None:
                continue
            rider_coords = (rider.latitude, rider.longitude)
            street_coords = resolve_street_coords(nearest_node.data, street_geometries)
            if street_coords is not None:
                proj_lat, proj_lon = project_point_on_street(rider_coords, street_coords)
            else:
                proj_lat, proj_lon = nearest_node.coords
            rider.latitude = float(proj_lat)
            rider.longitude = float(proj_lon)
            rider.geohash = geohash_encode(rider.latitude, rider.longitude, size=8)
        t5 = time.perf_counter_ns()
        t_street_projection_ms = (t5 - t4) / 1e6
        t_kdtree_snapping_ms = t_kdtree_nearest_ms + t_street_projection_ms

        # sub-tarefa 1.3: indexacao na radixtree e armazenamento no dicionario do sistema
        t6 = time.perf_counter_ns()
        riders_dict = {}
        radix_tree = RadixTree()
        for rider in riders:
            riders_dict[rider.id] = rider
            radix_tree.insert(rider.geohash, rider.id)
        t7 = time.perf_counter_ns()
        t_radix_index_ms = (t7 - t6) / 1e6

        # sub-tarefa 1.4a: construcao da featurecollection geojson para o mapa
        t8 = time.perf_counter_ns()
        features = [
            build_rider_feature(rider, status="normal")
            for rider in riders
            if rider.latitude is not None and rider.longitude is not None
        ]
        geojson = {"type": "FeatureCollection", "features": features}
        t9 = time.perf_counter_ns()
        t_geojson_build_ms = (t9 - t8) / 1e6

        # sub-tarefa 1.4b: serializacao json e compressao gzip para servir via rota http
        t10 = time.perf_counter_ns()
        _ = create_map_url(geojson, full_map=True)
        t11 = time.perf_counter_ns()
        t_gzip_compress_ms = (t11 - t10) / 1e6
    finally:
        gc.enable()

    t_creation_total_ms = t_sampling_ms + t_kdtree_snapping_ms + t_radix_index_ms
    t_render_prep_ms = t_geojson_build_ms + t_gzip_compress_ms
    t_total_ms = t_creation_total_ms + t_render_prep_ms
    throughput = num_riders / (t_total_ms / 1000.0) if t_total_ms > 0 else 0.0

    metrics = {
        "t_sampling_ms": t_sampling_ms,
        "t_kdtree_nearest_ms": t_kdtree_nearest_ms,
        "t_street_projection_ms": t_street_projection_ms,
        "t_kdtree_snapping_ms": t_kdtree_snapping_ms,
        "t_radix_index_ms": t_radix_index_ms,
        "t_creation_total_ms": t_creation_total_ms,
        "t_geojson_build_ms": t_geojson_build_ms,
        "t_gzip_compress_ms": t_gzip_compress_ms,
        "t_render_prep_ms": t_render_prep_ms,
        "t_total_ms": t_total_ms,
        "throughput_riders_s": throughput,
    }
    return metrics, riders_dict, radix_tree


def run_single_search_benchmark(
    system: DeliverySystem,
    bar: Any,
    radius_km: float,
    ranking_by: str = "time",
) -> dict[str, Any]:
    """executa e cronometra detalhadamente cada sub-tarefa da busca espacial e roteamento no raio"""
    radius_meters = float(radius_km) * 1000.0
    bar_geohash = bar.geohash or geohash_encode(bar.latitude, bar.longitude, size=8)

    gc.collect()
    gc.disable()
    try:
        # sub-tarefa 2.1: selecao de prefixo e busca das 9 celulas na radixtree
        t0 = time.perf_counter_ns()
        prefix_size = select_geohash_prefix_size(radius_meters)
        candidate_ids = search_candidates(system.radix_tree, bar_geohash, prefix_size=prefix_size)
        candidates = [
            system.get_rider(cid)
            for cid in candidate_ids
            if system.get_rider(cid) is not None
        ]
        t1 = time.perf_counter_ns()
        t_trie_search_ms = (t1 - t0) / 1e6

        # sub-tarefa 2.2: calculo de distancia haversine e filtragem pelo raio
        t2 = time.perf_counter_ns()
        restaurant_location = (bar.latitude, bar.longitude)
        classified = classify_candidates_by_distance(candidates, restaurant_location, radius_meters)
        filtered = filter_candidates_by_radius(classified)
        t3 = time.perf_counter_ns()
        t_haversine_filter_ms = (t3 - t2) / 1e6

        # sub-tarefa 2.3 e 2.4: associacao de nos na malha viaria e calculo de rotas mais rapidas
        t_nearest_nodes_ms = 0.0
        t_shortest_path_ms = 0.0
        road_network = system.road_network

        if road_network is not None and filtered:
            t4 = time.perf_counter_ns()
            bar_latitude, bar_longitude = restaurant_location
            longitudes = [bar_longitude] + [c["longitude"] for c in filtered]
            latitudes = [bar_latitude] + [c["latitude"] for c in filtered]
            nodes = ox.distance.nearest_nodes(road_network, X=longitudes, Y=latitudes)
            bar_node = nodes[0]
            rider_nodes = list(nodes[1:])
            t5 = time.perf_counter_ns()
            t_nearest_nodes_ms = (t5 - t4) / 1e6

            t6 = time.perf_counter_ns()
            routes = ox.routing.shortest_path(
                road_network,
                orig=rider_nodes,
                dest=[bar_node] * len(rider_nodes),
                weight="travel_time",
            )
            routed_filtered = []
            for candidate, route in zip(filtered, routes):
                result = {**candidate, "road_distance": None, "estimated_time": None}
                if route is not None:
                    if len(route) == 1:
                        result["road_distance"] = 0.0
                        result["estimated_time"] = 0.0
                    else:
                        total_length = 0.0
                        total_travel_time = 0.0
                        for u, v in zip(route[:-1], route[1:]):
                            edge_dict = road_network[u][v]
                            best_edge = min(
                                edge_dict.values(),
                                key=lambda d: d.get("travel_time", float("inf")),
                            )
                            total_length += best_edge.get("length", 0.0)
                            total_travel_time += best_edge.get("travel_time", 0.0)
                        result["road_distance"] = round(float(total_length), 2)
                        result["estimated_time"] = round(float(total_travel_time) / 60, 2)
                routed_filtered.append(result)
            filtered = routed_filtered
            t7 = time.perf_counter_ns()
            t_shortest_path_ms = (t7 - t6) / 1e6

        # sub-tarefa 2.5: ordenacao, montagem das features geojson (filtrados e descartados) e compressao
        t8 = time.perf_counter_ns()
        if ranking_by == "time":
            filtered.sort(
                key=lambda c: (
                    c.get("estimated_time") is None,
                    c.get("estimated_time") if c.get("estimated_time") is not None else float("inf"),
                    c.get("distance", float("inf")),
                )
            )
        else:
            filtered.sort(key=lambda c: c.get("distance", float("inf")))

        filtered_by_id = {c["id"]: c for c in filtered}
        filtered_features = []
        for info in filtered:
            rider = system.get_rider(info["id"])
            if rider is None or rider.latitude is None or rider.longitude is None:
                continue
            filtered_features.append(
                build_rider_feature(
                    rider,
                    status="filtered",
                    distance_meters=info.get("distance"),
                    road_distance_meters=info.get("road_distance"),
                    estimated_time_minutes=info.get("estimated_time"),
                    ranking_by=ranking_by,
                )
            )

        discarded_features = []
        for c in classified:
            if c["id"] in filtered_by_id:
                continue
            rider = system.get_rider(c["id"])
            if rider is None or rider.latitude is None or rider.longitude is None:
                continue
            discarded_features.append(
                build_rider_feature(
                    rider,
                    status="discarded",
                    distance_meters=c.get("distance"),
                )
            )

        geojson_filtered = {"type": "FeatureCollection", "features": filtered_features}
        geojson_discarded = {"type": "FeatureCollection", "features": discarded_features}
        _ = create_map_url(geojson_filtered)
        _ = create_map_url(geojson_discarded)
        t9 = time.perf_counter_ns()
        t_render_prep_ms = (t9 - t8) / 1e6
    finally:
        gc.enable()

    t_routing_total_ms = t_nearest_nodes_ms + t_shortest_path_ms
    t_total_ms = t_trie_search_ms + t_haversine_filter_ms + t_routing_total_ms + t_render_prep_ms

    return {
        "prefix_size": prefix_size,
        "trie_candidates": len(classified),
        "filtered_within_radius": len(filtered),
        "discarded_in_region": len(discarded_features),
        "t_trie_search_ms": t_trie_search_ms,
        "t_haversine_filter_ms": t_haversine_filter_ms,
        "t_nearest_nodes_ms": t_nearest_nodes_ms,
        "t_shortest_path_ms": t_shortest_path_ms,
        "t_routing_total_ms": t_routing_total_ms,
        "t_render_prep_ms": t_render_prep_ms,
        "t_total_ms": t_total_ms,
    }


def select_representative_bars(valid_bars: list[Any]) -> list[Any]:
    """seleciona um bar central representativo na regiao centro-sul (savassi/centro) para os testes"""
    # coordenadas aproximadas da praca da liberdade / savassi (-19.932, -43.938)
    target_lat, target_lon = -19.9320, -43.9380
    best_bar = min(
        valid_bars,
        key=lambda b: (b.latitude - target_lat) ** 2 + (b.longitude - target_lon) ** 2,
    )
    return [best_bar]


def main() -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)

    system, kdtree, street_geometries, init_metrics = measure_initialization()
    valid_bars = filter_valid_bars(system.bars.values())
    test_bars = select_representative_bars(valid_bars)
    primary_bar = test_bars[0]
    print(
        f"\nBar de referencia selecionado para buscas: ID={primary_bar.id} | "
        f"{primary_bar.nome_fantasia or primary_bar.nome} ({primary_bar.bairro}) "
        f"em ({primary_bar.latitude:.5f}, {primary_bar.longitude:.5f})"
    )

    # warm-up para aquecer caches internos de geracao, nearest_nodes e shortest_path
    print("\nExecutando warm-up inicial...")
    _, system.riders, system.radix_tree = run_single_generation_benchmark(
        valid_bars, 500, kdtree, street_geometries, seed=999
    )
    _ = run_single_search_benchmark(system, primary_bar, radius_km=1.0)
    system.riders = {}
    system.radix_tree = RadixTree()
    gc.collect()

    gen_raw_rows: list[dict[str, Any]] = []
    gen_summary_rows: list[dict[str, Any]] = []
    search_raw_rows: list[dict[str, Any]] = []
    search_summary_rows: list[dict[str, Any]] = []

    print("\n=== 1. Experimento de Geracao + Renderizacao e 2. Experimento de Busca no Raio ===")
    for n_riders in RIDER_COUNTS:
        print(f"\n--- Testando N = {n_riders:,} entregadores ---")
        iter_metrics_list = []
        repeats_gen = 3 if n_riders >= 50000 else GENERATION_REPEATS

        for rep in range(1, repeats_gen + 1):
            metrics, riders_dict, radix_tree = run_single_generation_benchmark(
                valid_bars=valid_bars,
                num_riders=n_riders,
                kdtree=kdtree,
                street_geometries=street_geometries,
                seed=40 + rep,
            )
            iter_metrics_list.append(metrics)
            del riders_dict
            del radix_tree
            gc.collect()

            row = {
                "n_riders": n_riders,
                "iteration": rep,
                **{k: round(v, 4) for k, v in metrics.items()},
            }
            gen_raw_rows.append(row)
            print(
                f"  [Geracao #{rep}] Total: {metrics['t_total_ms']:.2f} ms "
                f"(Criacao: {metrics['t_creation_total_ms']:.2f} ms [Amostragem: {metrics['t_sampling_ms']:.2f} ms, "
                f"KD-Tree+Snap: {metrics['t_kdtree_snapping_ms']:.2f} ms, Trie: {metrics['t_radix_index_ms']:.2f} ms] | "
                f"Render/GeoJSON: {metrics['t_render_prep_ms']:.2f} ms)"
            )

        # sumariza as repeticoes de geracao para este N
        metric_keys = list(iter_metrics_list[0].keys())
        summary_gen: dict[str, Any] = {"n_riders": n_riders, "repeats": repeats_gen}
        for k in metric_keys:
            vals = [m[k] for m in iter_metrics_list]
            summary_gen[f"{k}_mean"] = round(float(np.mean(vals)), 4)
            summary_gen[f"{k}_std"] = round(float(np.std(vals)), 4)
        gen_summary_rows.append(summary_gen)

        # injeta a populacao gerada (seed=42) no sistema para testar a busca
        _, system.riders, system.radix_tree = run_single_generation_benchmark(
            valid_bars=valid_bars,
            num_riders=n_riders,
            kdtree=kdtree,
            street_geometries=street_geometries,
            seed=42,
        )

        # executa a bateria de buscas para cada raio com a populacao atual N
        for radius_km in SEARCH_RADII_KM:
            search_iters = []
            repeats = 1 if (n_riders >= 50000 and radius_km >= 2.0) else SEARCH_REPEATS
            for s_rep in range(1, repeats + 1):
                s_metrics = run_single_search_benchmark(
                    system=system,
                    bar=primary_bar,
                    radius_km=radius_km,
                    ranking_by="time",
                )
                search_iters.append(s_metrics)
                s_row = {
                    "n_riders": n_riders,
                    "radius_km": radius_km,
                    "bar_id": primary_bar.id,
                    "iteration": s_rep,
                    "prefix_size": s_metrics["prefix_size"],
                    "trie_candidates": s_metrics["trie_candidates"],
                    "filtered_within_radius": s_metrics["filtered_within_radius"],
                    "discarded_in_region": s_metrics["discarded_in_region"],
                    "t_trie_search_ms": round(s_metrics["t_trie_search_ms"], 4),
                    "t_haversine_filter_ms": round(s_metrics["t_haversine_filter_ms"], 4),
                    "t_nearest_nodes_ms": round(s_metrics["t_nearest_nodes_ms"], 4),
                    "t_shortest_path_ms": round(s_metrics["t_shortest_path_ms"], 4),
                    "t_routing_total_ms": round(s_metrics["t_routing_total_ms"], 4),
                    "t_render_prep_ms": round(s_metrics["t_render_prep_ms"], 4),
                    "t_total_ms": round(s_metrics["t_total_ms"], 4),
                }
                search_raw_rows.append(s_row)

            # sumariza as repeticoes de busca para (N, radius_km)
            time_keys = [
                "t_trie_search_ms",
                "t_haversine_filter_ms",
                "t_nearest_nodes_ms",
                "t_shortest_path_ms",
                "t_routing_total_ms",
                "t_render_prep_ms",
                "t_total_ms",
            ]
            s_summary: dict[str, Any] = {
                "n_riders": n_riders,
                "radius_km": radius_km,
                "bar_id": primary_bar.id,
                "prefix_size": search_iters[0]["prefix_size"],
                "trie_candidates": search_iters[0]["trie_candidates"],
                "filtered_within_radius": search_iters[0]["filtered_within_radius"],
                "discarded_in_region": search_iters[0]["discarded_in_region"],
                "repeats": repeats,
            }
            for tk in time_keys:
                vals = [m[tk] for m in search_iters]
                s_summary[f"{tk}_mean"] = round(float(np.mean(vals)), 4)
                s_summary[f"{tk}_std"] = round(float(np.std(vals)), 4)
            search_summary_rows.append(s_summary)

            print(
                f"  [Busca R={radius_km}km | Prefixo={s_summary['prefix_size']}] "
                f"Cand. Trie: {s_summary['trie_candidates']} | No Raio: {s_summary['filtered_within_radius']} -> "
                f"Total: {s_summary['t_total_ms_mean']:.2f} ms "
                f"(Trie: {s_summary['t_trie_search_ms_mean']:.3f} ms, "
                f"Haversine: {s_summary['t_haversine_filter_ms_mean']:.3f} ms, "
                f"NearestNodes: {s_summary['t_nearest_nodes_ms_mean']:.2f} ms, "
                f"Rotas OSM: {s_summary['t_shortest_path_ms_mean']:.2f} ms, "
                f"GeoJSON: {s_summary['t_render_prep_ms_mean']:.3f} ms)"
            )

        system.riders = {}
        system.radix_tree = RadixTree()
        gc.collect()

    # salva os arquivos csv e json em experiments/results/
    def save_csv(path: Path, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        with open(path, mode="w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    save_csv(RESULTS_DIR / "generation_raw.csv", gen_raw_rows)
    save_csv(RESULTS_DIR / "generation_summary.csv", gen_summary_rows)
    save_csv(RESULTS_DIR / "search_raw.csv", search_raw_rows)
    save_csv(RESULTS_DIR / "search_summary.csv", search_summary_rows)

    full_report = {
        "initialization": init_metrics,
        "reference_bar": {
            "id": primary_bar.id,
            "name": primary_bar.nome_fantasia or primary_bar.nome,
            "neighborhood": primary_bar.bairro,
            "latitude": primary_bar.latitude,
            "longitude": primary_bar.longitude,
            "geohash": primary_bar.geohash,
        },
        "generation_summary": gen_summary_rows,
        "search_summary": search_summary_rows,
    }
    with open(RESULTS_DIR / "benchmark_summary.json", mode="w", encoding="utf-8") as f:
        json.dump(full_report, f, indent=2, ensure_ascii=False)

    print(f"\nExperimentos concluidos! Resultados salvos em: {RESULTS_DIR}")


if __name__ == "__main__":
    main()

