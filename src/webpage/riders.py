"""Funções e componentes da interface web para geração e exibição de entregadores."""

import threading
import time
from typing import Any, Iterable
from dash import dcc, html
import dash_bootstrap_components as dbc
import dash_leaflet as dl

from src.delivery_system.DeliverySystem import DeliverySystem
from src.generation.rider_generation import (
    filter_candidates_by_radius,
    get_segments_kdtree,
    get_street_geometries,
    load_segmentation_points,
)
from src.geo_index.geohash.geohashing import geohash_encode
from src.geometry.geometry_utilities import (
    classify_candidates_by_distance,
    haversine_distance,
)
from src.models.Bar import Bar
from src.models.Rider import Rider
from src.spatial_search.spatial_search import (
    osm_distance_and_time,
    search_candidates,
    select_geohash_prefix_size,
)
import osmnx as ox

DEFAULT_NUM_RIDERS = 200
DEFAULT_STD_DEV_METERS = 500.0
DEFAULT_SEARCH_RADIUS_KM = 2.0
RIDER_FILL_COLOR = "#ff6b00"
RIDER_BORDER_COLOR = "#ffffff"
MAX_GENERATION_BATCHES = 20

# referências às funções JavaScript em assets/riders_map.js para o dl.GeoJSON
RIDER_CLUSTER_TO_LAYER = {"variable": "ifeed.riderClusterToLayer"}
RIDER_DISCARDED_CLUSTER_TO_LAYER = {"variable": "ifeed.riderDiscardedClusterToLayer"}
RIDER_POINT_TO_LAYER = {"variable": "ifeed.riderPointToLayer"}

# estado global thread-safe para o carregamento inicial da malha viária e kd-tree
_INIT_LOCK = threading.Lock()
_INIT_STATE: dict[str, Any] = {
    "running": False,
    "percent": 0,
    "message": "Iniciando carregamento...",
    "ready": False,
}

# estado global thread-safe para acompanhamento da barra de progresso
_PROGRESS_LOCK = threading.Lock()
_GENERATION_STATE: dict[str, Any] = {
    "running": False,
    "percent": 0,
    "generated_so_far": 0,
    "target_total": 0,
    "total_riders": 0,
    "cleared": True,
    "message": "",
    "markers": [],
    "geojson": {"type": "FeatureCollection", "features": []},
}


def get_initialization_state() -> dict[str, Any]:
    """retorna uma cópia thread-safe do estado atual de inicialização da malha viária e kd-tree"""
    with _INIT_LOCK:
        return dict(_INIT_STATE)


def is_initialization_ready() -> bool:
    """informa se o carregamento da malha viária e a kd-tree já foram concluídos"""
    with _INIT_LOCK:
        return bool(_INIT_STATE["ready"])


def _set_init_state(
    percent: int,
    message: str,
    ready: bool = False,
    running: bool = True,
) -> None:
    with _INIT_LOCK:
        _INIT_STATE["percent"] = percent
        _INIT_STATE["message"] = message
        _INIT_STATE["ready"] = ready
        _INIT_STATE["running"] = running


def _run_initialization_worker(system: DeliverySystem | None = None) -> None:
    """executa em segundo plano o carregamento da malha viária e a montagem da kd-tree"""
    try:
        # 1. carregamento e leitura dos pontos de segmentação
        _set_init_state(percent=10, message="Lendo segmentos de ruas (data/segmentos_ruas_bh.csv.gz)...")
        load_segmentation_points()

        # 2. montagem da kd-tree com os pontos segmentados
        _set_init_state(percent=35, message="Montando KD-Tree das ruas (181.103 nós)...")
        get_segments_kdtree()

        # 3. carregamento do grafo da malha viária de bh com animação suave de progresso
        _set_init_state(percent=55, message="Carregando malha viária de BH (data/malha_viaria_bh.graphml)...")

        stop_ticker = threading.Event()

        def _ticker():
            cur = 55
            while not stop_ticker.wait(1.0):
                if cur < 82:
                    cur += 7
                    _set_init_state(percent=cur, message="Carregando nós e arestas da malha viária...")

        ticker_thread = threading.Thread(target=_ticker, daemon=True)
        ticker_thread.start()

        road_network = ox.load_graphml(filepath="data/malha_viaria_bh.graphml")
        stop_ticker.set()
        ticker_thread.join()

        if system is not None:
            system.road_network = road_network

        # 4. extração e indexação das geometrias das ruas
        _set_init_state(percent=90, message="Indexando geometrias das ruas...")
        get_street_geometries(road_network=road_network)

        # 5. inicialização concluída
        _set_init_state(
            percent=100,
            message="Malha viária e KD-Tree carregadas com sucesso!",
            ready=True,
            running=False,
        )
    except Exception as e:
        _set_init_state(
            percent=100,
            message=f"erro na inicialização: {e}",
            ready=True,
            running=False,
        )


def start_initialization_job(system: DeliverySystem | None = None) -> None:
    """inicia o carregamento da malha viária e a montagem da kd-tree em segundo plano"""
    with _INIT_LOCK:
        if _INIT_STATE["running"] or _INIT_STATE["ready"]:
            return
        _INIT_STATE.update({
            "running": True,
            "percent": 0,
            "message": "Iniciando carregamento...",
            "ready": False,
        })

    worker = threading.Thread(
        target=_run_initialization_worker,
        args=(system,),
        daemon=True,
    )
    worker.start()


def generate_and_store_riders(
    system: DeliverySystem,
    num_riders: int | None,
    clear_existing: bool = True,
    std_dev_meters: float = DEFAULT_STD_DEV_METERS,
    seed: int | None = None,
) -> list[Rider]:
    """Gera entregadores utilizando DeliverySystem.generate_riders()."""
    if num_riders is None or int(num_riders) <= 0:
        return []

    return system.generate_riders(
        num_riders=int(num_riders),
        std_dev_meters=std_dev_meters,
        seed=seed,
        clear_existing=bool(clear_existing),
    )


def format_estimated_time(minutes: float | None, is_ready: bool = True) -> str:
    """Formata o tempo estimado em minutos para exibição amigável."""
    if minutes is None:
        return "Calculando..." if not is_ready else "Sem rota"
    if minutes < 1.0:
        secs = round(minutes * 60)
        return f"{secs} s" if secs > 0 else "< 1 s"
    mins = int(minutes)
    secs = round((minutes - mins) * 60)
    if secs > 0:
        return f"{mins} min {secs} s"
    return f"{mins} min"


def format_road_distance(meters: float | None) -> str:
    """Formata a distância viária em metros para exibição amigável."""
    if meters is None:
        return "N/A"
    if meters < 1000:
        return f"{meters:.0f} m"
    return f"{meters / 1000.0:.2f} km"


def build_rider_feature(
    rider: Rider,
    status: str = "normal",
    distance_meters: float | None = None,
    road_distance_meters: float | None = None,
    estimated_time_minutes: float | None = None,
    ranking_by: str = "time",
) -> dict[str, Any]:
    """Converte um Rider em uma Feature GeoJSON contendo apenas dados numéricos e primitivos."""
    props: dict[str, Any] = {
        "id": rider.id,
        "geohash": rider.geohash,
        "status": status,
    }
    if distance_meters is not None:
        props["dist"] = distance_meters
    if road_distance_meters is not None:
        props["road_dist"] = road_distance_meters
    if estimated_time_minutes is not None:
        props["time"] = estimated_time_minutes
    if status == "filtered":
        props["ranking_by"] = ranking_by

    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [rider.longitude, rider.latitude],
        },
        "properties": props,
    }


def build_riders_geojson(riders: Iterable[Rider]) -> dict[str, Any]:
    """Converte uma coleção de entregadores em um FeatureCollection GeoJSON para clusterização."""
    features = [
        build_rider_feature(rider, status="normal")
        for rider in riders
        if rider.latitude is not None and rider.longitude is not None
    ]
    return {"type": "FeatureCollection", "features": features}


def search_and_build_riders_for_bar(
    system: DeliverySystem,
    bar: Bar,
    radius_km: float,
    ranking_by: str = "time",
) -> dict[str, Any]:
    """Busca entregadores na Trie (célula do bar + 8 adjacentes), filtra pelo raio,
    calcula rotas na malha viária e monta o GeoJSON ordenado por tempo de trajeto ou distância.
    """
    radius_meters = float(radius_km) * 1000.0
    bar_geohash = bar.geohash or geohash_encode(bar.latitude, bar.longitude, size=8)
    prefix_size = select_geohash_prefix_size(radius_meters)

    # 1. busca na RadixTree pela célula do bar e as 8 células adjacentes em O(m + k)
    candidate_ids = search_candidates(system.radix_tree, bar_geohash, prefix_size=prefix_size)
    candidates = [
        system.get_rider(cid)
        for cid in candidate_ids
        if system.get_rider(cid) is not None
    ]

    # 2. classificação por distância geométrica (Haversine) e filtragem por raio
    restaurant_location = (bar.latitude, bar.longitude)
    classified = classify_candidates_by_distance(candidates, restaurant_location, radius_meters)
    filtered = filter_candidates_by_radius(classified)

    # 3. se houver malha viária carregada, calcula distância pelas ruas e tempo de trajeto
    road_network = getattr(system, "road_network", None)
    if road_network is not None and filtered:
        try:
            filtered = osm_distance_and_time(road_network, filtered, restaurant_location)
        except Exception as err:
            print(f"Aviso no cálculo de rotas OSM: {err}")

    # 4. ordenação conforme critério escolhido: tempo de trajeto (default) ou distância
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

    # 5. construção das Features GeoJSON: apenas candidatos da região (Trie)
    # filtrados em destaque (laranja) e descartados da vizinhança em cinza
    filtered_features: list[dict[str, Any]] = []
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

    discarded_features: list[dict[str, Any]] = []
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

    geojson_filtered = {
        "type": "FeatureCollection",
        "features": filtered_features,
    }
    geojson_discarded = {
        "type": "FeatureCollection",
        "features": discarded_features,
    }
    geojson = {
        "type": "FeatureCollection",
        "features": discarded_features + filtered_features,
    }

    return {
        "geojson": geojson,
        "geojson_filtered": geojson_filtered,
        "geojson_discarded": geojson_discarded,
        "filtered": filtered,
        "trie_candidates_count": len(classified),
        "filtered_count": len(filtered_features),
        "discarded_trie_count": len(discarded_features),
        "discarded_total_count": len(discarded_features),
        "prefix_used": bar_geohash[:prefix_size],
        "prefix_size": prefix_size,
        "radius_km": float(radius_km),
        "radius_meters": radius_meters,
        "ranking_by": ranking_by,
    }


def _render_fallback_ranking_radio(value: str = "time") -> html.Div:
    """Renderiza um componente de rádio oculto para manter o ID persistente no DOM do Dash."""
    return html.Div(
        dbc.RadioItems(
            id="radio-ranking-criterion",
            options=[
                {"label": "Tempo de trajeto", "value": "time"},
                {"label": "Distância", "value": "distance"},
            ],
            value=value,
        ),
        style={"display": "none"},
    )


def render_nearby_search_results(
    bar: Bar | None = None,
    search_result: dict[str, Any] | None = None,
    total_system_riders: int = 0,
    invalid_radius: bool = False,
):
    """Renderiza o painel lateral com o resultado da busca de entregadores no raio de atendimento."""
    if invalid_radius:
        return html.Div([
            dbc.Alert(
                "Informe um raio de atendimento válido (maior que 0 km).",
                color="danger",
                className="small py-2 px-3 mb-0 mt-2",
            ),
            _render_fallback_ranking_radio(),
        ])

    if bar is None:
        return _render_fallback_ranking_radio()

    if total_system_riders <= 0:
        return html.Div([
            dbc.Alert(
                [
                    html.Strong("Nenhum entregador no mapa. "),
                    "Abra a aba ",
                    html.B("Entregadores"),
                    " abaixo e clique em ",
                    html.B("Gerar Entregadores"),
                    " para visualizar os entregadores no raio deste restaurante.",
                ],
                color="warning",
                className="small py-2 px-3 mb-0 mt-2",
            ),
            _render_fallback_ranking_radio(),
        ])

    if search_result is None:
        return _render_fallback_ranking_radio()

    filtered_list = search_result["filtered"]
    filtered_count = search_result["filtered_count"]
    discarded_total = search_result["discarded_total_count"]
    trie_count = search_result["trie_candidates_count"]
    discarded_trie = search_result["discarded_trie_count"]
    prefix_used = search_result["prefix_used"]
    radius_km = search_result["radius_km"]
    ranking_by = search_result.get("ranking_by", "time")
    is_ready = is_initialization_ready()

    rider_items = []
    for item in filtered_list[:50]:
        if ranking_by == "time":
            badge_label = format_estimated_time(item.get("estimated_time"), is_ready=is_ready)
            badge_title = "Tempo de trajeto estimado pelas ruas"
        else:
            dist_m = item["distance"]
            badge_label = f"{dist_m:.0f} m" if dist_m < 1000 else f"{dist_m / 1000.0:.2f} km ({dist_m:.0f} m)"
            badge_title = "Distância em linha reta ao restaurante"

        rider_items.append(
            html.Div(
                className="d-flex justify-content-between align-items-center py-1 border-bottom",
                children=[
                    html.Span(f"Entregador #{item['id']}", className="fw-semibold small"),
                    dbc.Badge(
                        badge_label,
                        color="warning",
                        text_color="dark",
                        className="font-monospace",
                        title=badge_title,
                    ),
                ],
            )
        )

    return dbc.Card(
        dbc.CardBody([
            html.H6("Entregadores no Raio de Atendimento", className="fw-bold mb-2"),
            html.Div(
                className="d-flex flex-wrap gap-1 mb-2",
                children=[
                    dbc.Badge(
                        f"{filtered_count} no raio ({radius_km:g} km)",
                        color="warning",
                        text_color="white",
                    ),
                    dbc.Badge(
                        f"{discarded_total} descartados na região",
                        color="secondary",
                    ),
                    dbc.Badge(
                        "Por tempo de trajeto" if ranking_by == "time" else "Por distância",
                        color="info",
                        text_color="white",
                    ),
                ],
            ),
            html.Div(
                className="small text-muted mb-2",
                style={"fontSize": "0.78rem"},
                children=[
                    html.Div([
                        html.Strong("Busca na Trie (Geohash): "),
                        html.Code(prefix_used),
                        html.Span(" + 8 células adjacentes"),
                    ]),
                    html.Div([
                        html.Strong("Candidatos na região: "),
                        html.Span(f"{trie_count} encontrados ({discarded_trie} fora do raio)"),
                    ]),
                ],
            ),
            html.Div(
                className="small mb-2 p-2 bg-light rounded border",
                style={"fontSize": "0.75rem"},
                children=[
                    html.Div([
                        html.Strong("Em destaque (laranja): "),
                        html.Span(f"dentro do raio (≤ {radius_km:g} km)"),
                    ]),
                    html.Div([
                        html.Strong("Sem destaque (cinza): "),
                        html.Span("entregadores descartados da região"),
                    ]),
                    html.Div([
                        html.Strong("Exibição ao lado: "),
                        html.Span(
                            "tempo estimado pelas ruas"
                            if ranking_by == "time"
                            else "distância em linha reta"
                        ),
                    ]),
                ],
            ),
            html.Div(
                className="d-flex justify-content-between align-items-center mb-1 mt-2 pt-1 border-top",
                children=[
                    html.Label(
                        "Ranquear por:",
                        className="fw-semibold small text-muted mb-0",
                        style={"fontSize": "0.78rem"},
                    ),
                    dbc.RadioItems(
                        id="radio-ranking-criterion",
                        options=[
                            {"label": "Tempo de trajeto", "value": "time"},
                            {"label": "Distância", "value": "distance"},
                        ],
                        value=ranking_by,
                        inline=True,
                        className="small",
                        style={"fontSize": "0.78rem"},
                    ),
                ],
            ),
            (
                html.Div(
                    style={"maxHeight": "160px", "overflowY": "auto"},
                    className="border rounded px-2 py-1 bg-white",
                    children=rider_items,
                )
                if filtered_count > 0
                else html.P(
                    f"Nenhum entregador encontrado a até {radius_km:g} km deste restaurante.",
                    className="small text-muted mb-0 fst-italic",
                )
            ),
        ]),
        className="border-warning shadow-sm mt-2",
    )


def render_rider_marker(rider: Rider) -> dl.CircleMarker:
    """Cria o marcador visual (CircleMarker) de um entregador para exibição no mapa."""
    return dl.CircleMarker(
        id=f"rider-marker-{rider.id}",
        center=[rider.latitude, rider.longitude],
        radius=6,
        color=RIDER_BORDER_COLOR,
        fillColor=RIDER_FILL_COLOR,
        fillOpacity=0.9,
        weight=1.5,
        children=[
            dl.Tooltip(f"Entregador #{rider.id}"),
            dl.Popup([
                html.B(f"Entregador #{rider.id}"),
                html.Br(),
                html.Small(f"Coordenadas: ({rider.latitude:.6f}, {rider.longitude:.6f})"),
                html.Br(),
                html.Small(f"Geohash: {rider.geohash or 'N/A'}"),
            ]),
        ],
    )


def render_riders_layer(riders: Iterable[Rider]) -> list[dl.CircleMarker]:
    """Converte os entregadores existentes em marcadores do dash-leaflet."""
    return [render_rider_marker(rider) for rider in riders]


def get_rider_generation_state() -> dict[str, Any]:
    """Retorna uma cópia thread-safe do estado atual de geração de entregadores."""
    with _PROGRESS_LOCK:
        return dict(_GENERATION_STATE)


def _run_generation_worker(
    system: DeliverySystem,
    num_riders: int,
    clear_existing: bool,
    std_dev_meters: float,
) -> None:
    """Executa a geração de entregadores em lotes atualizando o progresso."""
    num_batches = min(MAX_GENERATION_BATCHES, max(1, num_riders))
    base_batch = num_riders // num_batches
    remainder = num_riders % num_batches

    generated_so_far = 0

    for i in range(num_batches):
        batch_size = base_batch + (1 if i < remainder else 0)
        if batch_size <= 0:
            continue

        batch_clear = clear_existing if i == 0 else False
        batch_riders = generate_and_store_riders(
            system=system,
            num_riders=batch_size,
            clear_existing=batch_clear,
            std_dev_meters=std_dev_meters,
        )
        generated_so_far += len(batch_riders)
        percent = int((generated_so_far / num_riders) * 80)

        with _PROGRESS_LOCK:
            _GENERATION_STATE["generated_so_far"] = generated_so_far
            _GENERATION_STATE["percent"] = percent
            _GENERATION_STATE["message"] = (
                f"Gerando entregadores: {generated_so_far:,} / {num_riders:,}".replace(",", ".")
            )

        # cede o GIL brevemente para que o servidor Flask/Dash responda ao dcc.Interval
        time.sleep(0.015)

    # construção do GeoJSON clusterizado do mapa (80% -> 100%)
    all_riders = list(system.riders.values())
    total_in_system = len(all_riders)
    features: list[dict[str, Any]] = []
    step = max(1, total_in_system // 10)

    for idx, rider in enumerate(all_riders, start=1):
        if rider.latitude is not None and rider.longitude is not None:
            features.append(build_rider_feature(rider))
        if idx % step == 0 or idx == total_in_system:
            render_pct = 80 + int((idx / max(1, total_in_system)) * 20)
            with _PROGRESS_LOCK:
                _GENERATION_STATE["percent"] = min(99, render_pct)
                _GENERATION_STATE["message"] = (
                    f"Preparando mapa: {idx:,} / {total_in_system:,} entregadores".replace(",", ".")
                )
            time.sleep(0.01)

    with _PROGRESS_LOCK:
        _GENERATION_STATE["percent"] = 100
        _GENERATION_STATE["total_riders"] = total_in_system
        _GENERATION_STATE["geojson"] = {"type": "FeatureCollection", "features": features}
        _GENERATION_STATE["message"] = (
            f"Concluído! {generated_so_far:,} entregadores gerados.".replace(",", ".")
        )
        _GENERATION_STATE["running"] = False


def start_rider_generation_job(
    system: DeliverySystem,
    num_riders: int,
    clear_existing: bool = True,
    std_dev_meters: float = DEFAULT_STD_DEV_METERS,
) -> None:
    """Inicia a geração de entregadores em segundo plano para alimentar a barra de progresso."""
    with _PROGRESS_LOCK:
        if _GENERATION_STATE["running"]:
            return
        _GENERATION_STATE.update({
            "running": True,
            "percent": 0,
            "generated_so_far": 0,
            "target_total": int(num_riders),
            "total_riders": len(system.riders),
            "cleared": bool(clear_existing),
            "message": f"Gerando entregadores: 0 / {int(num_riders):,}".replace(",", "."),
            "markers": [],
            "geojson": {"type": "FeatureCollection", "features": []},
        })

    worker = threading.Thread(
        target=_run_generation_worker,
        args=(system, int(num_riders), bool(clear_existing), std_dev_meters),
        daemon=True,
    )
    worker.start()


def render_riders_status(
    total_riders: int,
    last_generated: int | None = None,
    cleared: bool = False,
    invalid_input: bool = False,
) -> html.Div:
    """Renderiza o indicador de quantidade de entregadores ativos no mapa."""
    children: list[Any] = [
        dbc.Badge(
            f"{total_riders:,} entregadores no mapa".replace(",", "."),
            color="warning" if total_riders > 0 else "secondary",
            text_color="dark" if total_riders > 0 else "white",
            className="me-1",
        )
    ]

    if invalid_input:
        children.append(
            html.Small(
                "Informe uma quantidade válida maior que zero.",
                className="text-danger d-block mt-1",
            )
        )
    elif last_generated is not None:
        acao = "substituídos" if cleared else "adicionados"
        children.append(
            html.Small(
                f"+{last_generated:,} entregadores gerados ({acao}).".replace(",", "."),
                className="text-success d-block mt-1",
            )
        )

    return html.Div(children)


def render_initialization_progress() -> html.Div:
    """renderiza a barra de progresso exibida durante o carregamento inicial da malha e kd-tree"""
    ready = is_initialization_ready()
    return html.Div(
        id="init-progress-container",
        style={"display": "none"} if ready else {"display": "block"},
        className="mb-3 p-3 bg-light border rounded shadow-sm",
        children=[
            html.Div(
                className="d-flex justify-content-between align-items-center mb-1",
                children=[
                    html.Span(
                        "Carregando malha viária e KD-Tree...",
                        className="fw-semibold small text-primary",
                        style={"fontSize": "0.78rem"},
                    ),
                    html.Small(
                        id="init-progress-percent-label",
                        children="0%",
                        className="text-muted fw-bold",
                        style={"fontSize": "0.75rem"},
                    ),
                ],
            ),
            dbc.Progress(
                id="init-progress-bar",
                value=0,
                color="primary",
                striped=True,
                animated=True,
                style={"height": "14px"},
            ),
            html.Small(
                id="init-progress-text",
                children="Iniciando carregamento...",
                className="text-muted d-block mt-1",
                style={"fontSize": "0.72rem"},
            ),
        ],
    )


def render_riders_controls(initial_total: int = 0, is_ready: bool | None = None) -> html.Div:
    """Renderiza a seção de controles e barra de progresso para geração de entregadores."""
    if is_ready is None:
        is_ready = is_initialization_ready()

    return html.Div([
        html.Label(
            "Gerar Entregadores:",
            className="fw-semibold small mb-1",
        ),
        dbc.InputGroup(
            [
                dbc.InputGroupText("Qtd."),
                dbc.Input(
                    id="input-num-riders",
                    type="number",
                    min=1,
                    max=50000,
                    step=1,
                    value=DEFAULT_NUM_RIDERS,
                    placeholder="Nº de entregadores",
                ),
            ],
            size="sm",
            className="mb-2",
        ),
        dbc.Checkbox(
            id="checkbox-clear-riders",
            label="Apagar entregadores existentes antes de gerar",
            value=True,
            className="small mb-2",
        ),
        dbc.Button(
            "Gerar Entregadores",
            id="btn-generate-riders",
            color="warning",
            size="sm",
            disabled=not is_ready,
            title="" if is_ready else "Aguarde até que o carregamento do mapa esteja concluído.",
            className="w-100 fw-semibold mb-2",
        ),
        # mensagem informativa exibida enquanto o mapa e a kd-tree estão sendo carregados
        html.Div(
            id="rider-init-warning",
            children="Aguarde até que o carregamento do mapa esteja concluído.",
            className="text-muted fst-italic text-center mb-2",
            style={"display": "none"} if is_ready else {"display": "block", "fontSize": "0.75rem"},
        ),
        # barra de progresso exibida durante a geração
        html.Div(
            id="rider-progress-container",
            style={"display": "none"},
            className="mb-2",
            children=[
                dbc.Progress(
                    id="rider-progress-bar",
                    value=0,
                    label="0%",
                    color="warning",
                    striped=True,
                    animated=True,
                    style={"height": "18px", "fontSize": "0.75rem"},
                ),
                html.Small(
                    id="rider-progress-text",
                    className="text-muted d-block mt-1",
                    style={"fontSize": "0.75rem"},
                ),
            ],
        ),
        dcc.Interval(
            id="interval-rider-progress",
            interval=100,
            disabled=True,
        ),
        html.Div(
            id="riders-status-container",
            children=render_riders_status(initial_total),
        ),
    ])
