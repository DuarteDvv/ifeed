r"""Interface web interativa do iFeed usando Dash e Dash-Leaflet.

Exibe o mapa de Belo Horizonte com os bares de data/bares_final.csv.gz
e permite buscar bares por nome, nome fantasia, endereço, bairro ou ID.

Execute com:
    .\.venv\Scripts\python.exe main.py
"""

import dash
from dash import Input, Output, State, callback, ctx, dcc, html
import dash_bootstrap_components as dbc
import dash_leaflet as dl

from src.generation.rider_generation import filter_valid_bars
from src.models.Bar import Bar
from src.webpage.map_navigation import (
    BAR_CLUSTER_TO_LAYER,
    BH_CENTER,
    BH_DEFAULT_ZOOM,
    MAX_DROPDOWN_OPTIONS,
    build_bar_indices,
    build_bars_geojson,
    filter_bar_options,
    find_bar_from_click,
    format_bar_option,
    init_bar_catalog,
    render_bar_details,
    render_highlighted_bar_layer,
)
from src.webpage.riders import (
    RIDER_CLUSTER_TO_LAYER,
    RIDER_POINT_TO_LAYER,
    build_riders_geojson,
    get_initialization_state,
    get_rider_generation_state,
    is_initialization_ready,
    render_initialization_progress,
    render_riders_controls,
    render_riders_status,
    start_initialization_job,
    start_rider_generation_job,
)

print("Carregando bares de data/bares_final.csv.gz...")
SYSTEM = init_bar_catalog()
# inicia imediatamente o carregamento da malha viária e a montagem da kd-tree em segundo plano
start_initialization_job(system=SYSTEM)
ALL_BARS_COUNT = len(SYSTEM.bars)
VALID_BARS: list[Bar] = sorted(
    filter_valid_bars(SYSTEM.bars.values()),
    key=lambda b: (b.nome_fantasia or b.nome or "", b.id),
)
VALID_BARS_COUNT = len(VALID_BARS)
print(f"Bares carregados: {ALL_BARS_COUNT} total | {VALID_BARS_COUNT} com coordenadas válidas.")
print("Carregamento concluído!\n")

SEARCH_INDEX, BARS_BY_BAIRRO, COORDS_INDEX, BAIRRO_OPTIONS = build_bar_indices(VALID_BARS)
ALL_BARS_GEOJSON = build_bars_geojson(VALID_BARS)
INITIAL_DROPDOWN_OPTIONS = [format_bar_option(b) for b in VALID_BARS[:MAX_DROPDOWN_OPTIONS]]

# Inicialização do app Dash com tema Bootstrap moderno
app = dash.Dash(
    __name__,
    title="iFeed - Mapa de Bares de BH",
    external_stylesheets=[dbc.themes.FLATLY],
)

app.layout = dbc.Container(
    fluid=True,
    className="p-0",
    children=[
        dbc.Row(
            className="g-0",
            children=[
                # Painel lateral de controle e busca
                dbc.Col(
                    width=12,
                    md=4,
                    lg=3,
                    className="bg-white border-end d-flex flex-column",
                    style={"height": "100vh", "overflowY": "auto", "padding": "20px"},
                    children=[
                        html.Div([
                            html.H4("iFeed BH", className="fw-bold text-primary mb-1"),
                            html.P(
                                "Mapa interativo e busca de bares de Belo Horizonte",
                                className="text-muted small mb-2",
                            ),
                            dbc.Badge(
                                f"{VALID_BARS_COUNT:,} bares no mapa".replace(",", "."),
                                color="success",
                                className="me-1",
                            ),
                            dbc.Badge(
                                f"{ALL_BARS_COUNT:,} cadastrados".replace(",", "."),
                                color="secondary",
                            ),
                        ]),
                        html.Hr(className="my-3"),

                        # Barra de progresso de inicialização da malha viária e KD-Tree
                        render_initialization_progress(),
                        dcc.Interval(
                            id="interval-init-progress",
                            interval=150,
                            disabled=is_initialization_ready(),
                        ),

                        # Seções colapsáveis: Bares e Entregadores
                        dbc.Accordion(
                            [
                                dbc.AccordionItem(
                                    item_id="section-bares",
                                    title="🍽️ Buscar e Visualizar Bares",
                                    children=[
                                        # 1. Filtro opcional por bairro
                                        html.Label("Filtrar por Bairro:", className="fw-semibold small mb-1"),
                                        dcc.Dropdown(
                                            id="bairro-dropdown",
                                            options=BAIRRO_OPTIONS,
                                            placeholder="Todos os bairros de BH...",
                                            clearable=True,
                                            searchable=True,
                                            className="mb-3 small",
                                        ),

                                        # 2. Busca por bar específico
                                        html.Label(
                                            "Buscar Bar (nome, endereço ou ID):",
                                            className="fw-semibold small mb-1",
                                        ),
                                        dcc.Dropdown(
                                            id="bar-dropdown",
                                            options=INITIAL_DROPDOWN_OPTIONS,
                                            placeholder="Digite para buscar um bar...",
                                            clearable=True,
                                            searchable=True,
                                            className="mb-2 small",
                                        ),
                                        html.Small(
                                            "Dica: digite parte do nome, rua ou ID para pesquisar entre todos os bares.",
                                            className="text-muted d-block mb-3",
                                            style={"fontSize": "0.75rem"},
                                        ),

                                        # Botão para voltar à visão geral de BH
                                        dbc.Button(
                                            "Visão Geral de BH",
                                            id="btn-reset-view",
                                            color="outline-primary",
                                            size="sm",
                                            className="w-100 mb-3",
                                        ),

                                        # 3. Detalhes do bar selecionado
                                        html.Label(
                                            "Bar Selecionado:",
                                            className="fw-semibold small mb-1",
                                        ),
                                        html.Div(
                                            id="bar-details-container",
                                            children=render_bar_details(None),
                                        ),
                                    ],
                                ),
                                dbc.AccordionItem(
                                    item_id="section-entregadores",
                                    title="🛵 Entregadores",
                                    children=[
                                        render_riders_controls(len(SYSTEM.riders)),
                                    ],
                                ),
                            ],
                            always_open=True,
                            start_collapsed=True,
                            active_item=[],
                            flush=False,
                            className="shadow-sm",
                        ),

                        # Controles de visibilidade das camadas no mapa
                        html.Div(
                            className="mt-3 p-3 bg-light rounded border",
                            children=[
                                html.Label(
                                    "Exibição no Mapa:",
                                    className="fw-semibold small text-muted text-uppercase d-block mb-2",
                                    style={"letterSpacing": "0.5px"},
                                ),
                                dbc.Switch(
                                    id="switch-toggle-bares",
                                    label="🍽️ Mostrar restaurantes",
                                    value=True,
                                    className="small mb-2 fw-semibold",
                                ),
                                dbc.Switch(
                                    id="switch-toggle-entregadores",
                                    label="🛵 Mostrar entregadores",
                                    value=True,
                                    className="small fw-semibold",
                                ),
                            ],
                        ),
                    ],
                ),

                # Área principal com o mapa Dash-Leaflet
                dbc.Col(
                    width=12,
                    md=8,
                    lg=9,
                    children=[
                        dl.Map(
                            id="map-bh",
                            center=BH_CENTER,
                            zoom=BH_DEFAULT_ZOOM,
                            preferCanvas=True,
                            style={"width": "100%", "height": "100vh"},
                            children=[
                                dl.TileLayer(
                                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
                                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                                    maxZoom=19,
                                ),
                                dl.LayersControl(
                                    id="layers-control",
                                    overlays=["Restaurantes", "Entregadores"],
                                    children=[
                                        # Camada clusterizada com os bares de BH
                                    dl.Overlay(
                                        dl.GeoJSON(
                                            id="geojson-bares",
                                            data=ALL_BARS_GEOJSON,
                                            cluster=True,
                                            zoomToBoundsOnClick=True,
                                            spiderfyOnMaxZoom=True,
                                            superClusterOptions={"radius": 80, "maxZoom": 16},
                                            clusterToLayer=BAR_CLUSTER_TO_LAYER,
                                        ),
                                        id="overlay-bares",
                                        name="Restaurantes",
                                        checked=True,
                                    ),
                                    # Camada clusterizada (em losango) com os entregadores do sistema
                                    dl.Overlay(
                                        dl.GeoJSON(
                                            id="geojson-entregadores",
                                            data=build_riders_geojson(SYSTEM.riders.values()),
                                            cluster=True,
                                            zoomToBoundsOnClick=True,
                                            spiderfyOnMaxZoom=True,
                                            superClusterOptions={"radius": 70, "maxZoom": 16},
                                            clusterToLayer=RIDER_CLUSTER_TO_LAYER,
                                            pointToLayer=RIDER_POINT_TO_LAYER,
                                        ),
                                        id="overlay-entregadores",
                                        name="Entregadores",
                                        checked=True,
                                    ),
                                ]),
                                # Camada de destaque para o bar selecionado na busca
                                dl.LayerGroup(id="layer-bar-selecionado"),
                            ],
                        ),
                    ],
                ),
            ],
        )
    ],
)


@callback(
    Output("overlay-bares", "checked"),
    Input("switch-toggle-bares", "value"),
)
def toggle_restaurants_visibility(show_restaurants: bool | None) -> bool:
    """Controla a visibilidade da camada de restaurantes no mapa."""
    return bool(show_restaurants)


@callback(
    Output("overlay-entregadores", "checked"),
    Input("switch-toggle-entregadores", "value"),
)
def toggle_riders_visibility(show_riders: bool | None) -> bool:
    """Controla a visibilidade da camada de entregadores no mapa."""
    return bool(show_riders)


@callback(
    Output("geojson-bares", "data"),
    Input("bairro-dropdown", "value"),
)
def update_map_bars_by_bairro(selected_bairro: str | None) -> dict:
    """Atualiza os bares exibidos no mapa quando um bairro específico é filtrado."""
    if not selected_bairro:
        return ALL_BARS_GEOJSON
    bars_in_bairro = BARS_BY_BAIRRO.get(selected_bairro, [])
    return build_bars_geojson(bars_in_bairro)


@callback(
    Output("bar-dropdown", "options"),
    Output("bar-dropdown", "value"),
    Input("bar-dropdown", "search_value"),
    Input("bairro-dropdown", "value"),
    Input("geojson-bares", "clickData"),
    Input("btn-reset-view", "n_clicks"),
    State("bar-dropdown", "value"),
)
def update_bar_dropdown(
    search_value: str | None,
    selected_bairro: str | None,
    geojson_click: dict | None,
    _reset_clicks: int | None,
    current_value: int | None,
):
    """Atualiza as opções do dropdown e seleciona o bar quando clicado no mapa."""
    triggered = ctx.triggered_id

    # 1. Clique no botão de reset
    if triggered == "btn-reset-view":
        return INITIAL_DROPDOWN_OPTIONS, None

    # 2. Mudança no filtro de bairro
    if triggered == "bairro-dropdown":
        candidate_bars = BARS_BY_BAIRRO.get(selected_bairro, []) if selected_bairro else VALID_BARS
        options = [format_bar_option(b) for b in candidate_bars[:MAX_DROPDOWN_OPTIONS]]
        return options, None

    # 3. Clique em um marcador no mapa
    if triggered == "geojson-bares":
        clicked_bar = find_bar_from_click(geojson_click, SYSTEM, COORDS_INDEX, VALID_BARS)
        if clicked_bar is None:
            return dash.no_update, dash.no_update

        candidate_bars = BARS_BY_BAIRRO.get(selected_bairro, []) if selected_bairro else VALID_BARS
        options = [format_bar_option(b) for b in candidate_bars[:MAX_DROPDOWN_OPTIONS]]
        if all(opt["value"] != clicked_bar.id for opt in options):
            options.insert(0, format_bar_option(clicked_bar))

        return options, clicked_bar.id

    # 4. Digitação na caixa de busca do dropdown (ou carregamento inicial)
    candidate_bars = BARS_BY_BAIRRO.get(selected_bairro, []) if selected_bairro else VALID_BARS
    options = filter_bar_options(
        search_value=search_value,
        candidate_bars=candidate_bars,
        search_index=SEARCH_INDEX,
        max_options=MAX_DROPDOWN_OPTIONS,
        current_value=current_value,
        system=SYSTEM,
    )
    return options, dash.no_update


@callback(
    Output("layer-bar-selecionado", "children"),
    Output("map-bh", "viewport"),
    Output("bar-details-container", "children"),
    Input("bar-dropdown", "value"),
    Input("btn-reset-view", "n_clicks"),
    Input("bairro-dropdown", "value"),
    prevent_initial_call=True,
)
def update_map_and_details(
    selected_bar_id: int | None,
    _reset_clicks: int | None,
    selected_bairro: str | None,
):
    """Atualiza a aba 'Bar Selecionado', o pino destacado e a navegação da câmera."""
    triggered = ctx.triggered_id

    # 1. Botão de visão geral
    if triggered == "btn-reset-view":
        return (
            [],
            {"center": BH_CENTER, "zoom": BH_DEFAULT_ZOOM, "transition": "flyTo"},
            render_bar_details(None),
        )

    # 2. Mudança no filtro de bairro
    if triggered == "bairro-dropdown":
        if selected_bairro and selected_bairro in BARS_BY_BAIRRO:
            bars_bairro = BARS_BY_BAIRRO[selected_bairro]
            mean_lat = sum(b.latitude for b in bars_bairro) / len(bars_bairro)
            mean_lon = sum(b.longitude for b in bars_bairro) / len(bars_bairro)
            return (
                [],
                {"center": [mean_lat, mean_lon], "zoom": 15, "transition": "flyTo"},
                render_bar_details(None),
            )
        return (
            [],
            {"center": BH_CENTER, "zoom": BH_DEFAULT_ZOOM, "transition": "flyTo"},
            render_bar_details(None),
        )

    # 3. Bar selecionado (ou desmarcado)
    if selected_bar_id is None:
        return [], dash.no_update, render_bar_details(None)

    bar = SYSTEM.get_bar(int(selected_bar_id))
    if bar is None or bar.latitude is None or bar.longitude is None:
        return [], dash.no_update, render_bar_details(None)

    return (
        render_highlighted_bar_layer(bar),
        {"center": [bar.latitude, bar.longitude], "zoom": 17, "transition": "flyTo"},
        render_bar_details(bar),
    )


@callback(
    Output("geojson-entregadores", "data"),
    Output("riders-status-container", "children"),
    Output("rider-progress-container", "style"),
    Output("rider-progress-bar", "value"),
    Output("rider-progress-bar", "label"),
    Output("rider-progress-bar", "color"),
    Output("rider-progress-bar", "animated"),
    Output("rider-progress-text", "children"),
    Output("interval-rider-progress", "disabled"),
    Output("btn-generate-riders", "disabled", allow_duplicate=True),
    Input("btn-generate-riders", "n_clicks"),
    Input("interval-rider-progress", "n_intervals"),
    State("input-num-riders", "value"),
    State("checkbox-clear-riders", "value"),
    prevent_initial_call=True,
)
def handle_generate_riders(
    _n_clicks: int | None,
    _n_intervals: int | None,
    num_riders: int | None,
    clear_existing: bool | None,
):
    """Gerencia o início e a barra de progresso da geração de entregadores."""
    triggered = ctx.triggered_id

    # 1. Clique no botão "Gerar Entregadores"
    if triggered == "btn-generate-riders":
        if num_riders is None or int(num_riders) <= 0:
            return (
                dash.no_update,
                render_riders_status(len(SYSTEM.riders), invalid_input=True),
                {"display": "none"},
                0,
                "0%",
                "warning",
                False,
                "",
                True,
                False,
            )

        start_rider_generation_job(
            system=SYSTEM,
            num_riders=int(num_riders),
            clear_existing=bool(clear_existing),
        )
        return (
            dash.no_update,
            dash.no_update,
            {"display": "block"},
            0,
            "0%",
            "warning",
            True,
            f"Gerando entregadores: 0 / {int(num_riders):,}".replace(",", "."),
            False,
            True,
        )

    # 2. Atualização periódica da barra de progresso via dcc.Interval
    state = get_rider_generation_state()
    pct = state["percent"]

    if state["running"]:
        return (
            dash.no_update,
            dash.no_update,
            {"display": "block"},
            pct,
            f"{pct}%",
            "warning",
            True,
            state["message"],
            False,
            True,
        )

    # 3. Geração concluída: atualiza o mapa e finaliza a barra em 100%
    return (
        state["geojson"],
        render_riders_status(
            total_riders=state["total_riders"],
            last_generated=state["generated_so_far"],
            cleared=state["cleared"],
        ),
        {"display": "block"},
        100,
        "100%",
        "success",
        False,
        state["message"],
        True,
        False,
    )


@callback(
    Output("init-progress-container", "style"),
    Output("init-progress-bar", "value"),
    Output("init-progress-percent-label", "children"),
    Output("init-progress-text", "children"),
    Output("btn-generate-riders", "disabled", allow_duplicate=True),
    Output("btn-generate-riders", "title", allow_duplicate=True),
    Output("rider-init-warning", "style"),
    Output("interval-init-progress", "disabled"),
    Input("interval-init-progress", "n_intervals"),
    prevent_initial_call="initial_duplicate",
)
def update_initialization_progress(_n_intervals: int | None):
    """atualiza a barra de progresso da malha viária e kd-tree e habilita o botão ao concluir"""
    state = get_initialization_state()
    pct = state["percent"]
    message = state["message"]
    ready = state["ready"]

    if ready:
        return (
            {"display": "none"},
            100,
            "100%",
            message,
            False,
            "",
            {"display": "none"},
            True,
        )

    return (
        {"display": "block"},
        pct,
        f"{pct}%",
        message,
        True,
        "Aguarde até que o carregamento do mapa esteja concluído.",
        {"display": "block", "fontSize": "0.75rem"},
        False,
    )


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8050)