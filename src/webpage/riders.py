"""Funções e componentes da interface web para geração e exibição de entregadores."""

import threading
import time
from typing import Any, Iterable
from dash import dcc, html
import dash_bootstrap_components as dbc
import dash_leaflet as dl

from src.delivery_system.DeliverySystem import DeliverySystem
from src.generation.rider_generation import (
    get_segments_kdtree,
    get_street_geometries,
    load_segmentation_points,
)
from src.models.Rider import Rider
import osmnx as ox

DEFAULT_NUM_RIDERS = 200
DEFAULT_STD_DEV_METERS = 500.0
RIDER_FILL_COLOR = "#ff6b00"
RIDER_BORDER_COLOR = "#ffffff"
MAX_GENERATION_BATCHES = 20

# Referências às funções JavaScript em assets/riders_map.js para o dl.GeoJSON
RIDER_CLUSTER_TO_LAYER = {"variable": "ifeed.riderClusterToLayer"}
RIDER_POINT_TO_LAYER = {"variable": "ifeed.riderPointToLayer"}

# estado global thread-safe para o carregamento inicial da malha viária e kd-tree
_INIT_LOCK = threading.Lock()
_INIT_STATE: dict[str, Any] = {
    "running": False,
    "percent": 0,
    "message": "Iniciando carregamento...",
    "ready": False,
}

# Estado global thread-safe para acompanhamento da barra de progresso
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


def build_rider_feature(rider: Rider) -> dict[str, Any]:
    """Converte um Rider em uma Feature GeoJSON com tooltip e popup."""
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [rider.longitude, rider.latitude],
        },
        "properties": {
            "id": rider.id,
            "geohash": rider.geohash,
            "tooltip": f"🛵 Entregador #{rider.id}",
            "popup": (
                f"<b>🛵 Entregador #{rider.id}</b><br>"
                f"<b>Coordenadas:</b> ({rider.latitude:.6f}, {rider.longitude:.6f})<br>"
                f"<b>Geohash:</b> {rider.geohash or 'N/A'}"
            ),
        },
    }


def build_riders_geojson(riders: Iterable[Rider]) -> dict[str, Any]:
    """Converte uma coleção de entregadores em um FeatureCollection GeoJSON para clusterização."""
    features = [
        build_rider_feature(rider)
        for rider in riders
        if rider.latitude is not None and rider.longitude is not None
    ]
    return {"type": "FeatureCollection", "features": features}


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
            dl.Tooltip(f"🛵 Entregador #{rider.id}"),
            dl.Popup([
                html.B(f"🛵 Entregador #{rider.id}"),
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

        # Cede o GIL brevemente para que o servidor Flask/Dash responda ao dcc.Interval
        time.sleep(0.015)

    # Construção do GeoJSON clusterizado do mapa (80% -> 100%)
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
    children = [
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
                        "🗺️ Carregando malha viária e KD-Tree...",
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
        # Barra de progresso exibida durante a geração
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
