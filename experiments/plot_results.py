"""gera graficos a partir dos resultados experimentais coletados em experiments/results"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT_DIR / "experiments" / "results"


def plot_all() -> None:
    summary_path = RESULTS_DIR / "benchmark_summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {summary_path}")

    with open(summary_path, mode="r", encoding="utf-8") as f:
        data = json.load(f)

    gen_summary = data["generation_summary"]
    search_summary = data["search_summary"]

    plt.rcParams.update({
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.labelsize": 10,
        "figure.dpi": 150,
    })

    # figura 1: decomposicao do tempo de geracao de entregadores (absoluto e percentual)
    n_labels = [f"{row['n_riders']:,}".replace(",", ".") for row in gen_summary]
    x = np.arange(len(n_labels))

    t_sampling = np.array([row["t_sampling_ms_mean"] for row in gen_summary])
    t_kdtree = np.array([row["t_kdtree_nearest_ms_mean"] for row in gen_summary])
    t_proj = np.array([row["t_street_projection_ms_mean"] for row in gen_summary])
    t_radix = np.array([row["t_radix_index_ms_mean"] for row in gen_summary])
    t_geojson = np.array([row["t_geojson_build_ms_mean"] for row in gen_summary])
    t_gzip = np.array([row["t_gzip_compress_ms_mean"] for row in gen_summary])
    t_total = np.array([row["t_total_ms_mean"] for row in gen_summary])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5))

    # subplot 1a: tempo absoluto em barras empilhadas (escala linear)
    b1 = ax1.bar(x, t_sampling, label="1.1 Amostragem Normal + Instanciacao", color="#4e79a7")
    b2 = ax1.bar(x, t_kdtree, bottom=t_sampling, label="1.2a Busca na KD-Tree (nearest)", color="#f28e2b")
    b3 = ax1.bar(
        x,
        t_proj,
        bottom=t_sampling + t_kdtree,
        label="1.2b Projecao na Rua + Geohash",
        color="#e15759",
    )
    b4 = ax1.bar(
        x,
        t_radix,
        bottom=t_sampling + t_kdtree + t_proj,
        label="1.3 Indexacao na RadixTree",
        color="#76b7b2",
    )
    b5 = ax1.bar(
        x,
        t_geojson + t_gzip,
        bottom=t_sampling + t_kdtree + t_proj + t_radix,
        label="1.4 Renderizacao (GeoJSON + Gzip)",
        color="#59a14f",
    )

    for idx, tot in enumerate(t_total):
        ax1.text(
            idx,
            tot + max(t_total) * 0.015,
            f"{tot:.1f} ms",
            ha="center",
            va="bottom",
            fontsize=8.5,
            fontweight="bold",
        )

    ax1.set_xticks(x)
    ax1.set_xticklabels(n_labels)
    ax1.set_xlabel("Numero de Entregadores Gerados (N)")
    ax1.set_ylabel("Tempo de Processamento (ms)")
    ax1.set_title("Tempo de Geracao e Renderizacao por Sub-tarefa")
    ax1.grid(axis="y", linestyle="--", alpha=0.4)
    ax1.legend(loc="upper left", fontsize=8.5)

    # subplot 1b: proporcao percentual de cada sub-tarefa (criacao vs renderizacao)
    p_sampling = (t_sampling / t_total) * 100
    p_kdtree = (t_kdtree / t_total) * 100
    p_proj = (t_proj / t_total) * 100
    p_radix = (t_radix / t_total) * 100
    p_render = ((t_geojson + t_gzip) / t_total) * 100

    ax2.bar(x, p_sampling, label="1.1 Amostragem Normal", color="#4e79a7")
    ax2.bar(x, p_kdtree, bottom=p_sampling, label="1.2a Busca KD-Tree", color="#f28e2b")
    ax2.bar(x, p_proj, bottom=p_sampling + p_kdtree, label="1.2b Projecao + Geohash", color="#e15759")
    ax2.bar(
        x,
        p_radix,
        bottom=p_sampling + p_kdtree + p_proj,
        label="1.3 Indexacao RadixTree",
        color="#76b7b2",
    )
    ax2.bar(
        x,
        p_render,
        bottom=p_sampling + p_kdtree + p_proj + p_radix,
        label="1.4 Renderizacao (GeoJSON + Gzip)",
        color="#59a14f",
    )

    ax2.set_xticks(x)
    ax2.set_xticklabels(n_labels)
    ax2.set_ylim(0, 105)
    ax2.set_xlabel("Numero de Entregadores Gerados (N)")
    ax2.set_ylabel("Proporcao do Tempo Total (%)")
    ax2.set_title("Distribuicao Percentual do Tempo por Sub-tarefa")
    ax2.grid(axis="y", linestyle="--", alpha=0.4)

    plt.tight_layout()
    fig.savefig(RESULTS_DIR / "fig1_geracao_subtarefas.png", dpi=160)
    plt.close(fig)

    # figura 2: desempenho da busca no raio de um restaurante
    fig2, (ax2_1, ax2_2) = plt.subplots(1, 2, figsize=(10, 5))

    radii = sorted(list({row["radius_km"] for row in search_summary}))
    colors_r = {0.5: "#4e79a7", 1.0: "#f28e2b", 2.0: "#e15759"}

    for r_km in radii:
        rows_r = [row for row in search_summary if row["radius_km"] == r_km]
        n_vals = [row["n_riders"] for row in rows_r]
        y_vals = [row["t_total_ms_mean"] for row in rows_r]
        y_stds = [row["t_total_ms_std"] for row in rows_r]
        pref = rows_r[0]["prefix_size"]
        ax2_1.errorbar(
            range(len(n_vals)),
            y_vals,
            yerr=y_stds,
            marker="o",
            linewidth=2,
            capsize=4,
            color=colors_r.get(r_km, "#333333"),
            label=f"Raio = {r_km} km (Geohash prefix={pref})",
        )

    ax2_1.set_xticks(range(len(n_labels)))
    ax2_1.set_xticklabels(n_labels)
    ax2_1.set_xlabel("Total de Entregadores no Sistema (N)")
    ax2_1.set_ylabel("Tempo Total da Busca + Roteamento (ms)")
    ax2_1.set_title("Escalabilidade da Busca por Raio")
    ax2_1.grid(True, linestyle="--", alpha=0.4)
    ax2_1.legend()

    # subplot 2b: decomposicao das sub-tarefas de busca para R = 1.0 km
    rows_r1 = [row for row in search_summary if row["radius_km"] == 1.0]
    s_trie = np.array([row["t_trie_search_ms_mean"] for row in rows_r1])
    s_hav = np.array([row["t_haversine_filter_ms_mean"] for row in rows_r1])
    s_nn = np.array([row["t_nearest_nodes_ms_mean"] for row in rows_r1])
    s_sp = np.array([row["t_shortest_path_ms_mean"] for row in rows_r1])
    s_ren = np.array([row["t_render_prep_ms_mean"] for row in rows_r1])
    s_tot = np.array([row["t_total_ms_mean"] for row in rows_r1])

    ax2_2.bar(x, s_trie + s_hav, label="2.1 + 2.2 Busca RadixTree + Filtro Haversine", color="#4e79a7")
    ax2_2.bar(
        x,
        s_nn,
        bottom=s_trie + s_hav,
        label="2.3 Associacao de Nos no Grafo (nearest_nodes)",
        color="#f28e2b",
    )
    ax2_2.bar(
        x,
        s_sp,
        bottom=s_trie + s_hav + s_nn,
        label="2.4 Calculo de Rotas Viarias (shortest_path)",
        color="#e15759",
    )
    ax2_2.bar(
        x,
        s_ren,
        bottom=s_trie + s_hav + s_nn + s_sp,
        label="2.5 Renderizacao GeoJSON + Compressao",
        color="#59a14f",
    )

    for idx, (tot, row) in enumerate(zip(s_tot, rows_r1)):
        cands = row["filtered_within_radius"]
        ax2_2.text(
            idx,
            tot + max(s_tot) * 0.015,
            f"{tot:.1f} ms",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    ax2_2.set_xticks(x)
    ax2_2.set_xticklabels(n_labels)
    ax2_2.set_ylim(0, max(s_tot) * 1.15)
    ax2_2.set_xlabel("Total de Entregadores no Sistema (N)")
    ax2_2.set_ylabel("Tempo de Processamento (ms)")
    ax2_2.set_title("Decomposicao das Sub-tarefas de Busca\n(Raio = 1.0 km)")
    ax2_2.grid(axis="y", linestyle="--", alpha=0.4)
    ax2_2.legend(loc="upper left", fontsize=8.5)

    plt.tight_layout()
    fig2.savefig(RESULTS_DIR / "fig2_busca_raio_subtarefas.png", dpi=160)
    plt.close(fig2)

    # figura 3: comparacao em escala logaritmica (filtragem espacial pura vs roteamento viario)
    fig3, (ax3_1, ax3_2) = plt.subplots(1, 2, figsize=(12, 5.5))

    width = 0.25
    ax3_1.bar(x - width, [r["n_riders"] for r in rows_r1], width=width, label="Total no Sistema (N)", color="#bab0ac")
    ax3_1.bar(
        x,
        [r["trie_candidates"] for r in rows_r1],
        width=width,
        label="Candidatos na RadixTree (9 celulas)",
        color="#4e79a7",
    )
    ax3_1.bar(
        x + width,
        [r["filtered_within_radius"] for r in rows_r1],
        width=width,
        label="Dentro do Raio de 1.0 km (Haversine)",
        color="#e15759",
    )
    ax3_1.set_yscale("log")
    ax3_1.set_xticks(x)
    ax3_1.set_xticklabels(n_labels)
    ax3_1.set_xlabel("Total de Entregadores no Sistema (N)")
    ax3_1.set_ylabel("Quantidade de Entregadores (escala log)")
    ax3_1.set_title("Reducao do Espaco de Busca (Trie -> Haversine -> Rotas)")
    ax3_1.grid(axis="y", linestyle="--", alpha=0.4)
    ax3_1.legend()

    ax3_2.plot(x, s_trie, marker="o", linewidth=2, label="2.1 Busca RadixTree (9 celulas)", color="#4e79a7")
    ax3_2.plot(x, s_hav, marker="s", linewidth=2, label="2.2 Filtro Haversine", color="#76b7b2")
    ax3_2.plot(x, s_ren, marker="^", linewidth=2, label="2.5 Montagem GeoJSON + Gzip", color="#59a14f")
    ax3_2.plot(x, s_nn, marker="d", linewidth=2, label="2.3 Nearest Nodes (Grafo)", color="#f28e2b")
    ax3_2.plot(x, s_sp, marker="v", linewidth=2, label="2.4 Shortest Path (Dijkstra)", color="#e15759")
    ax3_2.set_yscale("log")
    ax3_2.set_xticks(x)
    ax3_2.set_xticklabels(n_labels)
    ax3_2.set_xlabel("Total de Entregadores no Sistema (N)")
    ax3_2.set_ylabel("Tempo por Sub-tarefa em ms (escala log)")
    ax3_2.set_title("Tempo de Cada Sub-tarefa da Busca em Escala Logaritmica (R = 1.0 km)")
    ax3_2.grid(True, which="both", linestyle="--", alpha=0.4)
    ax3_2.legend(fontsize=8.5)

    plt.tight_layout()
    fig3.savefig(RESULTS_DIR / "fig3_eficiencia_filtragem_log.png", dpi=160)
    plt.close(fig3)

    print(f"Graficos gerados com sucesso em: {RESULTS_DIR}")


if __name__ == "__main__":
    plot_all()

