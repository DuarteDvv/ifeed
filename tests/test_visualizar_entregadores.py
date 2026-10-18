"""Teste visual da geração de entregadores segundo a distribuição Normal.
Gera lojas de exemplo em Belo Horizonte, gera entregadores em torno delas e plota o mapa.

Execute com: python tests/test_visualizar_entregadores.py
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib.pyplot as plt
import numpy as np

from src.generation.rider_generation import (
    METERS_PER_DEGREE,
    calculate_bar_quotas,
    generate_riders_data,
)
from src.models.Bar import Bar


def criar_lojas_exemplo():
    """Gera lojas de exemplo em diferentes regiões de Belo Horizonte."""
    return [
        Bar(
            id=1,
            nome="Bar Savassi",
            nome_fantasia="Savassi Choperia",
            endereco="Rua Pernambuco, 1000",
            bairro="Savassi",
            latitude=-19.9385,
            longitude=-43.9355,
        ),
        Bar(
            id=2,
            nome="Bar Pampulha",
            nome_fantasia="Lagoa Bar & Grill",
            endereco="Av. Otacílio Negrão de Lima, 3000",
            bairro="Pampulha",
            latitude=-19.8515,
            longitude=-43.9725,
        ),
        Bar(
            id=3,
            nome="Bar Mercado Central",
            nome_fantasia="Fígado com Jiló",
            endereco="Av. Augusto de Lima, 744",
            bairro="Centro",
            latitude=-19.9225,
            longitude=-43.9425,
        ),
        Bar(
            id=4,
            nome="Bar Buritis",
            nome_fantasia="Buritis Gastrobar",
            endereco="Av. Professor Mário Werneck, 1500",
            bairro="Buritis",
            latitude=-19.9680,
            longitude=-43.9650,
        ),
    ]


def plotar_mapa_entregadores(lojas, entregadores, std_dev_meters=500.0, caminho_saida="tests/visualizacoes/mapa_entregadores.png"):
    """Plota as lojas e os entregadores em um mapa, exibindo a dispersão normal em torno de cada loja."""
    fig, (ax_mapa, ax_zoom) = plt.subplots(1, 2, figsize=(16, 7), gridspec_kw={"width_ratios": [1.2, 1]})

    # paleta de cores para identificar cada cluster de loja/entregadores
    cores = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]

    # identifica a qual loja cada entregador pertence usando a menor distância
    entregadores_por_loja = {loja.id: [] for loja in lojas}
    for r in entregadores:
        loja_mais_proxima = min(
            lojas,
            key=lambda l: (r.latitude - l.latitude) ** 2 + (r.longitude - l.longitude) ** 2,
        )
        entregadores_por_loja[loja_mais_proxima.id].append(r)

    # 1. painel da esquerda: Visão Geral de Belo Horizonte
    for i, loja in enumerate(lojas):
        cor = cores[i % len(cores)]
        riders_loja = entregadores_por_loja[loja.id]

        lats = [r.latitude for r in riders_loja]
        lons = [r.longitude for r in riders_loja]

        # entregadores (nuvem de dispersão)
        ax_mapa.scatter(
            lons, lats,
            color=cor, alpha=0.5, s=20,
            label=f"Entregadores ({loja.bairro}) - {len(riders_loja)} pts",
        )

        # loja (estrela destacada)
        ax_mapa.scatter(
            loja.longitude, loja.latitude,
            color=cor, edgecolor="black", marker="*", s=300, linewidth=1.5,
            zorder=10,
        )

    ax_mapa.set_title("Distribuição Normal dos Entregadores em Torno das Lojas (BH)", fontsize=13, fontweight="bold")
    ax_mapa.set_xlabel("Longitude", fontsize=11)
    ax_mapa.set_ylabel("Latitude", fontsize=11)
    ax_mapa.grid(True, linestyle="--", alpha=0.5)
    ax_mapa.legend(loc="upper left", fontsize=9, framealpha=0.9)

    # 2. painel da direita: Zoom detalhado em uma das lojas (Savassi) com círculos de 1σ e 2σ
    loja_foco = lojas[0]
    riders_foco = entregadores_por_loja[loja_foco.id]
    cor_foco = cores[0]

    lats_foco = [r.latitude for r in riders_foco]
    lons_foco = [r.longitude for r in riders_foco]

    ax_zoom.scatter(lons_foco, lats_foco, color=cor_foco, alpha=0.6, s=35, label="Entregadores")
    ax_zoom.scatter(
        loja_foco.longitude, loja_foco.latitude,
        color="red", edgecolor="black", marker="*", s=400, linewidth=2,
        label=f"Loja: {loja_foco.nome}", zorder=10,
    )

    # círculos de dispersão teóricos: 1σ (500m) e 2σ (1000m)
    raio_1sigma_deg = std_dev_meters / METERS_PER_DEGREE
    raio_2sigma_deg = (2 * std_dev_meters) / METERS_PER_DEGREE

    theta = np.linspace(0, 2 * np.pi, 200)
    c1_lon = loja_foco.longitude + raio_1sigma_deg * np.cos(theta)
    c1_lat = loja_foco.latitude + raio_1sigma_deg * np.sin(theta)
    c2_lon = loja_foco.longitude + raio_2sigma_deg * np.cos(theta)
    c2_lat = loja_foco.latitude + raio_2sigma_deg * np.sin(theta)

    ax_zoom.plot(c1_lon, c1_lat, "r--", linewidth=2, label=f"Raio 1σ ({int(std_dev_meters)}m)")
    ax_zoom.plot(c2_lon, c2_lat, "m:", linewidth=2, label=f"Raio 2σ ({int(2 * std_dev_meters)}m)")

    # estatística observada no cluster
    dists = [
        math.sqrt((r.latitude - loja_foco.latitude) ** 2 + (r.longitude - loja_foco.longitude) ** 2) * METERS_PER_DEGREE
        for r in riders_foco
    ]
    pct_1sigma = (sum(1 for d in dists if d <= std_dev_meters) / len(dists)) * 100 if dists else 0
    pct_2sigma = (sum(1 for d in dists if d <= 2 * std_dev_meters) / len(dists)) * 100 if dists else 0

    ax_zoom.set_title(
        f"Zoom no Cluster ({loja_foco.bairro})\n1σ={pct_1sigma:.1f}% (teórico ~63%), 2σ={pct_2sigma:.1f}% (teórico ~86%)",
        fontsize=12, fontweight="bold",
    )
    ax_zoom.set_xlabel("Longitude", fontsize=11)
    ax_zoom.set_ylabel("Latitude", fontsize=11)
    ax_zoom.axis("equal")
    ax_zoom.grid(True, linestyle="--", alpha=0.5)
    ax_zoom.legend(loc="upper right", fontsize=9, framealpha=0.9)

    plt.tight_layout()
    plt.savefig(caminho_saida, dpi=200)
    print(f"[OK] Imagem do mapa salva com sucesso em: {caminho_saida}")

    # exibe a janela gráfica interativa se houver display disponível
    try:
        plt.show()
    except Exception:
        pass


def gerar_mapa_interativo_leaflet(lojas, entregadores, std_dev_meters=500.0, caminho_html="tests/visualizacoes/mapa_entregadores.html"):
    """Gera mapa interativo HTML com Leaflet e OpenStreetMap de Belo Horizonte."""
    centro_lat = np.mean([l.latitude for l in lojas])
    centro_lon = np.mean([l.longitude for l in lojas])
    cores_hex = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]

    entregadores_por_loja = {loja.id: [] for loja in lojas}
    for r in entregadores:
        loja_mais_proxima = min(
            lojas,
            key=lambda l: (r.latitude - l.latitude) ** 2 + (r.longitude - l.longitude) ** 2,
        )
        entregadores_por_loja[loja_mais_proxima.id].append(r)

    lojas_json = []
    for i, loja in enumerate(lojas):
        cor = cores_hex[i % len(cores_hex)]
        pts = [{"lat": r.latitude, "lon": r.longitude, "id": r.id} for r in entregadores_por_loja[loja.id]]
        lojas_json.append({
            "id": loja.id,
            "nome": loja.nome,
            "bairro": loja.bairro,
            "lat": loja.latitude,
            "lon": loja.longitude,
            "cor": cor,
            "riders": pts,
        })

    import json
    dados_str = json.dumps(lojas_json)

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <title>Mapa de Entregadores - ifeed</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        html, body, #map {{ width: 100%; height: 100%; margin: 0; padding: 0; }}
        .painel {{ position: absolute; top: 10px; right: 10px; z-index: 1000; background: white; padding: 12px 16px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.3); font-family: sans-serif; }}
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="painel">
        <h4 style="margin: 0 0 8px;">Entregadores - Distribuição Normal</h4>
        <p style="margin: 4px 0; font-size: 13px;">Desvio padrão (σ): {int(std_dev_meters)}m</p>
        <p style="margin: 4px 0; font-size: 13px;">Círculo 1σ: {int(std_dev_meters)}m | Círculo 2σ: {int(2*std_dev_meters)}m</p>
    </div>
    <script>
        const map = L.map('map').setView([{centro_lat}, {centro_lon}], 12);
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 19,
            attribution: '© OpenStreetMap'
        }}).addTo(map);

        const dados = {dados_str};
        dados.forEach(loja => {{
            // marcador da loja
            L.circleMarker([loja.lat, loja.lon], {{
                radius: 10, fillColor: loja.cor, color: '#000', weight: 2, fillOpacity: 1
            }}).addTo(map).bindPopup(`<b>${{loja.nome}}</b> (${{loja.bairro}})`);

            // raio de 1 sigma (500m)
            L.circle([loja.lat, loja.lon], {{
                radius: {std_dev_meters}, color: loja.cor, weight: 2, dashArray: '5, 5', fillOpacity: 0.1
            }}).addTo(map);

            // raio de 2 sigma (1000m)
            L.circle([loja.lat, loja.lon], {{
                radius: {2*std_dev_meters}, color: loja.cor, weight: 1.5, dashArray: '2, 6', fill: false
            }}).addTo(map);

            // marcadores dos entregadores
            loja.riders.forEach(r => {{
                L.circleMarker([r.lat, r.lon], {{
                    radius: 4, fillColor: loja.cor, color: '#fff', weight: 1, fillOpacity: 0.75
                }}).addTo(map).bindPopup(`Entregador ${{r.id}}`);
            }});
        }});
    </script>
</body>
</html>"""

    with open(caminho_html, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[OK] Mapa interativo HTML salvo em: {caminho_html}")


def main():
    print("=== Teste Visual da Geração de Entregadores (Distribuição Normal) ===")

    # 1. criação das lojas de exemplo
    lojas = criar_lojas_exemplo()
    print(f"Lojas de exemplo criadas: {len(lojas)}")
    for l in lojas:
        print(f" - {l.nome} ({l.bairro}): ({l.latitude}, {l.longitude})")

    # 2. geração de múltiplos entregadores (ex: 800 entregadores distribuídos nas 4 lojas)
    total_entregadores = 800
    std_dev_meters = 500.0
    print(f"\nGerando {total_entregadores} entregadores (desvio padrão: {std_dev_meters}m)...")
    entregadores = generate_riders_data(
        bars=lojas,
        num_riders=total_entregadores,
        std_dev_meters=std_dev_meters,
        seed=123,
    )

    # 3. validações numéricas
    assert len(entregadores) == total_entregadores, f"Esperado {total_entregadores}, obtido {len(entregadores)}"
    assert len(set(r.id for r in entregadores)) == total_entregadores, "IDs duplicados encontrados"
    print(f"Total de entregadores gerados: {len(entregadores)} com IDs únicos.")

    # 4. plotagem dos mapas
    print("\nPlotando posições no mapa...")
    plotar_mapa_entregadores(lojas, entregadores, std_dev_meters=std_dev_meters)
    gerar_mapa_interativo_leaflet(lojas, entregadores, std_dev_meters=std_dev_meters)

    print("\nTeste concluído com sucesso!")


if __name__ == "__main__":
    main()

