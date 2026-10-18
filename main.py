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
    get_zoom_for_radius,
    init_bar_catalog,
    render_bar_details,
    render_highlighted_bar_layer,
)
from src.webpage.map_data import EMPTY_MAP_URL, create_map_url, register_map_route
from src.webpage.riders import (
    DEFAULT_SEARCH_RADIUS_KM,
    RIDER_CLUSTER_TO_LAYER,
    RIDER_DISCARDED_CLUSTER_TO_LAYER,
    RIDER_POINT_TO_LAYER,
    get_initialization_state,
    get_rider_generation_state,
    is_initialization_ready,
    render_initialization_progress,
    render_nearby_search_results,
    render_riders_controls,
    render_riders_status,
    search_and_build_riders_for_bar,
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

def get_all_riders_map_url() -> str:
    """Retorna a URL já preparada pelo gerador, sem reconstruir os pontos."""
    return get_rider_generation_state()["map_url"] or EMPTY_MAP_URL


# inicialização do app Dash com tema Bootstrap moderno
app = dash.Dash(
    __name__,
    title="iFeed - Mapa de Bares de BH",
    external_stylesheets=[dbc.themes.FLATLY],
    suppress_callback_exceptions=True,
)

register_map_route(app.server)

app.layout = dbc.Container(
    fluid=True,
    className="p-0",
    children=[
        dcc.Store(id="riders-ready", data=False),
        dcc.Store(id="riders-map-visible"),
        dbc.Row(
            className="g-0",
            children=[
                # painel lateral de controle e busca
                dbc.Col(
                    width=12,
                    md=4,
                    lg=3,
                    className="bg-white border-end d-flex flex-column",
                    style={"height": "100vh", "overflowY": "auto", "padding": "20px"},
                    children=[
                        html.Div([
                            html.H4("iFeed", className="fw-bold text-primary mb-1"),
                            html.P(
                                "Eduardo Birchal e Luis Duarte",
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

                        # barra de progresso de inicialização da malha viária e KD-Tree
                        render_initialization_progress(),
                        dcc.Interval(
                            id="interval-init-progress",
                            interval=150,
                            disabled=is_initialization_ready(),
                        ),

                        dbc.Alert(
                            [
                                html.Strong("Primeiro, gere os entregadores."),
                                html.Div("Na seção Entregadores, informe a quantidade e clique em Gerar Entregadores. Depois, escolha um bar no mapa ou na busca."),
                            ],
                            id="generate-riders-first-notice",
                            color="warning",
                            is_open=True,
                            className="small mb-3",
                        ),

                        # seções colapsáveis: Bares e Entregadores
                        dbc.Accordion(
                            [
                                dbc.AccordionItem(
                                    item_id="section-bares",
                                    title="Buscar e Visualizar Bares",
                                    children=[
                                        # 1. filtro opcional por bairro
                                        html.Label("Filtrar por Bairro:", className="fw-semibold small mb-1"),
                                        dcc.Dropdown(
                                            id="bairro-dropdown",
                                            options=BAIRRO_OPTIONS,
                                            placeholder="Todos os bairros de BH...",
                                            clearable=True,
                                            searchable=True,
                                            className="mb-3 small",
                                        ),

                                        # 2. busca por bar específico
                                        html.Label(
                                            "Buscar Bar (nome, endereço ou ID):",
                                            className="fw-semibold small mb-1",
                                        ),
                                        dcc.Dropdown(
                                            id="bar-dropdown",
                                            options=INITIAL_DROPDOWN_OPTIONS,
                                            placeholder="Gere os entregadores para escolher um bar...",
                                            disabled=True,
                                            clearable=True,
                                            searchable=True,
                                            className="mb-2 small",
                                        ),
                                        html.Small(
                                            "Gere os entregadores na aba Entregadores para liberar a seleção de bares.",
                                            id="bar-selection-hint",
                                            className="text-muted d-block mb-3",
                                            style={"fontSize": "0.75rem"},
                                        ),

                                        # 3. parâmetro de raio de atendimento e busca de entregadores
                                        html.Label(
                                            "Raio de Atendimento (km):",
                                            className="fw-semibold small mb-1",
                                        ),
                                        dbc.InputGroup(
                                            [
                                                dbc.InputGroupText("Raio"),
                                                dbc.Input(
                                                    id="input-search-radius-km",
                                                    type="number",
                                                    min=0.1,
                                                    max=50.0,
                                                    step=0.1,
                                                    value=DEFAULT_SEARCH_RADIUS_KM,
                                                    placeholder="Ex: 2.0",
                                                ),
                                                dbc.InputGroupText("km"),
                                            ],
                                            size="sm",
                                            className="mb-2",
                                        ),
                                        dbc.Button(
                                            "Buscar Entregadores no Raio",
                                            id="btn-search-nearby-riders",
                                            disabled=True,
                                            color="warning",
                                            size="sm",
                                            className="w-100 fw-semibold mb-2",
                                        ),

                                        # botão para voltar à visão geral de BH e limpar filtro
                                        dbc.Button(
                                            "Visão Geral de BH / Limpar Filtro",
                                            id="btn-reset-view",
                                            color="outline-primary",
                                            size="sm",
                                            className="w-100 mb-3",
                                        ),

                                    ],
                                ),
                                dbc.AccordionItem(
                                    item_id="section-entregadores",
                                    title="Entregadores",
                                    children=[
                                        render_riders_controls(len(SYSTEM.riders)),
                                    ],
                                ),
                            ],
                            always_open=True,
                            start_collapsed=True,
                            active_item=["section-entregadores"],
                            flush=False,
                            className="shadow-sm",
                        ),

                        # controles de visibilidade das camadas no mapa
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
                                    label="Mostrar restaurantes",
                                    value=True,
                                    className="small mb-2 fw-semibold",
                                ),
                                dbc.Switch(
                                    id="switch-toggle-entregadores",
                                    label="Mostrar entregadores",
                                    value=True,
                                    className="small fw-semibold",
                                ),
                            ],
                        ),
                    ],
                ),

                # área principal com o mapa Dash-Leaflet
                dbc.Col(
                    width=12,
                    md=8,
                    lg=9,
                    className="map-container",
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
                                        # camada clusterizada com os bares de BH
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
                                    # camadas clusterizadas (em losango): entregadores descartados (cinza) e normais/filtrados (laranja)
                                    dl.Overlay(
                                        dl.LayerGroup(
                                            id="layer-group-entregadores",
                                            children=[
                                                dl.GeoJSON(
                                                    id="geojson-entregadores-descartados",
                                                    data={"type": "FeatureCollection", "features": []},
                                                    cluster=True,
                                                    zoomToBoundsOnClick=True,
                                                    spiderfyOnMaxZoom=True,
                                                    superClusterOptions={"radius": 70, "maxZoom": 16},
                                                    clusterToLayer=RIDER_DISCARDED_CLUSTER_TO_LAYER,
                                                    pointToLayer=RIDER_POINT_TO_LAYER,
                                                ),
                                                dl.GeoJSON(
                                                    id="geojson-entregadores",
                                                    url=get_all_riders_map_url(),
                                                    eventHandlers={"layeradd": {"variable": "ifeed.ridersMapLayerAdded"}},
                                                    cluster=True,
                                                    zoomToBoundsOnClick=True,
                                                    spiderfyOnMaxZoom=True,
                                                    superClusterOptions={"radius": 70, "maxZoom": 16},
                                                    clusterToLayer=RIDER_CLUSTER_TO_LAYER,
                                                    pointToLayer=RIDER_POINT_TO_LAYER,
                                                ),
                                            ],
                                        ),
                                        id="overlay-entregadores",
                                        name="Entregadores",
                                        checked=True,
                                    ),
                                ]),
                                # camada de destaque para o bar selecionado na busca
                                dl.LayerGroup(id="layer-bar-selecionado"),
                            ],
                        ),
                        html.Div(
                            id="map-overview-legend",
                            className="map-selection-legend map-overview-legend",
                            hidden=False,
                            children=[
                                html.Strong("Legenda — visão geral", className="d-block mb-1"),
                                html.Div([
                                    html.Span(className="legend-symbol legend-bar-cluster-small"),
                                    html.Span(className="legend-symbol legend-bar-cluster-medium"),
                                    html.Span(className="legend-symbol legend-bar-cluster-large"),
                                    "Círculos: grupos de bares",
                                ]),
                                html.Div([
                                    html.Span(className="legend-symbol legend-rider"),
                                    "Losangos laranja: grupos de entregadores",
                                ]),
                                html.P("O número indica quantos pontos estão agrupados.", className="mb-0 mt-2"),
                                html.P("Cores e tamanhos variam conforme a quantidade.", className="mb-0"),
                                html.P("Aproxime o mapa para ver os pontos separados.", className="mb-0 text-muted"),
                            ],
                        ),
                        html.Div(
                            id="map-selection-legend",
                            className="map-selection-legend",
                            hidden=True,
                            children=[
                                html.Strong("Legenda", className="d-block mb-1"),
                                html.Div([html.Span(className="legend-symbol legend-bar"), "Bar selecionado"]),
                                html.Div([html.Span(className="legend-symbol legend-rider"), "Entregadores dentro do raio"]),
                                html.Div([html.Span(className="legend-symbol legend-discarded"), "Entregadores fora do raio na região"]),
                                html.Div([html.Span(className="legend-symbol legend-radius"), "Raio de atendimento"]),
                            ],
                        ),
                        html.Details(
                            open=True,
                            className="map-search-results map-bar-details",
                            children=[
                                html.Summary([
                                    html.Span("Bar selecionado", className="fw-semibold"),
                                    html.Span("Minimizar −", className="panel-minimize-label"),
                                    html.Span("Expandir +", className="panel-expand-label"),
                                ], className="map-results-toggle"),
                                html.Div(
                                    id="bar-details-container",
                                    children=render_bar_details(None),
                                ),
                            ],
                        ),
                        html.Details(
                            open=True,
                            className="map-search-results",
                            children=[
                                html.Summary([
                                    html.Span("Entregadores no raio", className="fw-semibold"),
                                    html.Span("Minimizar −", className="panel-minimize-label"),
                                    html.Span("Expandir +", className="panel-expand-label"),
                                ], className="map-results-toggle"),
                                html.Div(
                                    id="nearby-search-results-container",
                                    children=render_nearby_search_results(None),
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )
    ],
)


app.clientside_callback(
    """function(visibleUrl, currentUrl, ready) {
        if (ready && visibleUrl && visibleUrl === currentUrl) {
            return "Mapa atualizado. Entregadores disponíveis para busca.";
        }
        return window.dash_clientside.no_update;
    }""",
    Output("rider-progress-text", "children", allow_duplicate=True),
    Input("riders-map-visible", "data"),
    Input("riders-ready", "data"),
    State("geojson-entregadores", "url"),
    prevent_initial_call=True,
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
    Output("bar-dropdown", "disabled"),
    Output("bar-dropdown", "placeholder"),
    Output("bar-selection-hint", "children"),
    Output("generate-riders-first-notice", "is_open"),
    Input("riders-ready", "data"),
)
def update_bar_selection_availability(ready: bool):
    if ready:
        return False, "Digite para buscar um bar...", "Digite parte do nome, rua ou ID, ou clique em um bar no mapa.", False
    return True, "Gere os entregadores para escolher um bar...", "Gere os entregadores na aba Entregadores para liberar a seleção de bares.", True


@callback(
    Output("btn-search-nearby-riders", "disabled"),
    Output("btn-search-nearby-riders", "title"),
    Output("map-selection-legend", "hidden"),
    Output("map-overview-legend", "hidden"),
    Input("riders-ready", "data"),
    Input("bar-dropdown", "value"),
)
def update_nearby_search_availability(ready: bool, selected_bar_id: int | None):
    bar = SYSTEM.get_bar(int(selected_bar_id)) if selected_bar_id is not None else None
    selected = bool(ready and bar is not None and bar.latitude is not None and bar.longitude is not None)
    if not ready:
        hint = "Gere os entregadores primeiro."
    elif not selected:
        hint = "Selecione um bar no mapa ou na busca."
    else:
        hint = "Buscar entregadores no raio do bar selecionado."
    return not selected, hint, not selected, selected


@callback(
    Output("geojson-bares", "data"),
    Input("bairro-dropdown", "value"),
    Input("bar-dropdown", "value"),
    Input("riders-ready", "data"),
)
def update_map_bars_by_bairro(selected_bairro: str | None, selected_bar_id: int | None, riders_ready: bool) -> dict:
    """Atualiza os bares exibidos no mapa quando um bairro específico é filtrado."""
    if riders_ready and selected_bar_id is not None and SYSTEM.get_bar(int(selected_bar_id)) is not None:
        # O bar selecionado já aparece na camada de destaque.
        return {"type": "FeatureCollection", "features": []}
    if not selected_bairro:
        return ALL_BARS_GEOJSON
    bars_in_bairro = BARS_BY_BAIRRO.get(selected_bairro, [])
    return build_bars_geojson(bars_in_bairro)


@callback(
    Output("bairro-dropdown", "value"),
    Output("input-search-radius-km", "value"),
    Output("bar-dropdown", "search_value"),
    Input("btn-reset-view", "n_clicks"),
    prevent_initial_call=True,
)
def reset_search_filters(_n_clicks: int | None):
    """Limpa bairro e texto da busca e restaura o raio padrão; o bar é limpo no dropdown."""
    return None, DEFAULT_SEARCH_RADIUS_KM, ""


@callback(
    Output("bar-dropdown", "options"),
    Output("bar-dropdown", "value"),
    Input("bar-dropdown", "search_value"),
    Input("bairro-dropdown", "value"),
    Input("geojson-bares", "clickData"),
    Input("btn-reset-view", "n_clicks"),
    Input("riders-ready", "data"),
    State("bar-dropdown", "value"),
)
def update_bar_dropdown(
    search_value: str | None,
    selected_bairro: str | None,
    geojson_click: dict | None,
    _reset_clicks: int | None,
    riders_ready: bool,
    current_value: int | None,
):
    """Atualiza as opções do dropdown e seleciona o bar quando clicado no mapa."""
    triggered = ctx.triggered_id
    if not riders_ready or get_rider_generation_state()["running"] or not SYSTEM.riders:
        return INITIAL_DROPDOWN_OPTIONS, None

    # 1. clique no botão de reset
    if triggered == "btn-reset-view":
        return INITIAL_DROPDOWN_OPTIONS, None

    # 2. mudança no filtro de bairro
    if triggered == "bairro-dropdown":
        candidate_bars = BARS_BY_BAIRRO.get(selected_bairro, []) if selected_bairro else VALID_BARS
        options = [format_bar_option(b) for b in candidate_bars[:MAX_DROPDOWN_OPTIONS]]
        return options, None

    # 3. clique em um marcador no mapa
    if triggered == "geojson-bares":
        clicked_bar = find_bar_from_click(geojson_click, SYSTEM, COORDS_INDEX, VALID_BARS)
        if clicked_bar is None:
            return dash.no_update, dash.no_update

        candidate_bars = BARS_BY_BAIRRO.get(selected_bairro, []) if selected_bairro else VALID_BARS
        options = [format_bar_option(b) for b in candidate_bars[:MAX_DROPDOWN_OPTIONS]]
        if all(opt["value"] != clicked_bar.id for opt in options):
            options.insert(0, format_bar_option(clicked_bar))

        return options, clicked_bar.id

    # 4. digitação na caixa de busca do dropdown (ou carregamento inicial)
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
    Output("nearby-search-results-container", "children", allow_duplicate=True),
    Output("geojson-entregadores", "url", allow_duplicate=True),
    Output("geojson-entregadores-descartados", "data", allow_duplicate=True),
    Input("bar-dropdown", "value"),
    Input("btn-search-nearby-riders", "n_clicks"),
    Input("input-search-radius-km", "value"),
    Input("radio-ranking-criterion", "value"),
    Input("btn-reset-view", "n_clicks"),
    Input("bairro-dropdown", "value"),
    Input("riders-ready", "data"),
    prevent_initial_call=True,
)
def update_map_and_details(
    selected_bar_id: int | None,
    _search_clicks: int | None,
    radius_km: float | None,
    ranking_criterion: str | None,
    _reset_clicks: int | None,
    selected_bairro: str | None,
    riders_ready: bool,
):
    """Atualiza o bar selecionado, o círculo de raio, a busca de entregadores e a câmera."""
    triggered = ctx.triggered_id
    empty_discarded = {"type": "FeatureCollection", "features": []}

    # se uma geração de entregadores estiver em andamento, encerra qualquer análise de bar anterior
    gen_state = get_rider_generation_state()
    if gen_state.get("running") or not riders_ready or not SYSTEM.riders:
        return (
            [],
            dash.no_update,
            render_bar_details(None),
            render_nearby_search_results(None),
            dash.no_update,
            empty_discarded,
        )

    # 1. botão de visão geral / limpar filtro
    if triggered == "btn-reset-view":
        return (
            [],
            {"center": BH_CENTER, "zoom": BH_DEFAULT_ZOOM, "transition": "flyTo"},
            render_bar_details(None),
            render_nearby_search_results(None),
            get_all_riders_map_url(),
            empty_discarded,
        )

    # 2. mudança no filtro de bairro
    if triggered == "bairro-dropdown":
        if selected_bairro and selected_bairro in BARS_BY_BAIRRO:
            bars_bairro = BARS_BY_BAIRRO[selected_bairro]
            mean_lat = sum(b.latitude for b in bars_bairro) / len(bars_bairro)
            mean_lon = sum(b.longitude for b in bars_bairro) / len(bars_bairro)
            return (
                [],
                {"center": [mean_lat, mean_lon], "zoom": 15, "transition": "flyTo"},
                render_bar_details(None),
                render_nearby_search_results(None),
                get_all_riders_map_url(),
                empty_discarded,
            )
        return (
            [],
            {"center": BH_CENTER, "zoom": BH_DEFAULT_ZOOM, "transition": "flyTo"},
            render_bar_details(None),
            render_nearby_search_results(None),
            get_all_riders_map_url(),
            empty_discarded,
        )

    # 3. nenhum bar selecionado (ou desmarcado)
    if selected_bar_id is None:
        # Só restaura os pontos quando a seleção ou o bairro são limpos.
        map_url = dash.no_update
        if triggered in ("bar-dropdown", "bairro-dropdown"):
            map_url = get_all_riders_map_url()
        return (
            [],
            dash.no_update,
            render_bar_details(None),
            render_nearby_search_results(None),
            map_url,
            empty_discarded,
        )

    bar = SYSTEM.get_bar(int(selected_bar_id))
    if bar is None or bar.latitude is None or bar.longitude is None:
        return (
            [],
            dash.no_update,
            render_bar_details(None),
            render_nearby_search_results(None),
            get_all_riders_map_url(),
            empty_discarded,
        )

    # 4. validação do raio de atendimento informado na interface
    if radius_km is None or float(radius_km) <= 0:
        return (
            render_highlighted_bar_layer(bar),
            {"center": [bar.latitude, bar.longitude], "zoom": 16, "transition": "flyTo"},
            render_bar_details(bar),
            render_nearby_search_results(bar=bar, invalid_radius=True),
            get_all_riders_map_url(),
            empty_discarded,
        )

    radius_val = float(radius_km)
    radius_meters = radius_val * 1000.0
    zoom_level = get_zoom_for_radius(radius_val)
    viewport = {"center": [bar.latitude, bar.longitude], "zoom": zoom_level, "transition": "flyTo"}

    # 6. executa a busca na Trie (célula + adjacentes), filtra pelo raio e plota filtrados vs descartados clusterizados
    ranking_by = ranking_criterion if ranking_criterion in ("time", "distance") else "time"
    search_result = search_and_build_riders_for_bar(SYSTEM, bar, radius_val, ranking_by=ranking_by)

    return (
        render_highlighted_bar_layer(bar, radius_meters=radius_meters),
        viewport,
        render_bar_details(bar),
        render_nearby_search_results(
            bar=bar,
            search_result=search_result,
            total_system_riders=len(SYSTEM.riders),
        ),
        create_map_url(search_result["geojson_filtered"]),
        search_result["geojson_discarded"],
    )


@callback(
    Output("geojson-entregadores", "url"),
    Output("geojson-entregadores-descartados", "data"),
    Output("nearby-search-results-container", "children", allow_duplicate=True),
    Output("riders-status-container", "children"),
    Output("rider-progress-container", "style"),
    Output("rider-progress-bar", "value"),
    Output("rider-progress-bar", "label"),
    Output("rider-progress-bar", "color"),
    Output("rider-progress-bar", "animated"),
    Output("rider-progress-text", "children"),
    Output("interval-rider-progress", "disabled"),
    Output("btn-generate-riders", "disabled", allow_duplicate=True),
    Output("bar-dropdown", "value", allow_duplicate=True),
    Output("layer-bar-selecionado", "children", allow_duplicate=True),
    Output("bar-details-container", "children", allow_duplicate=True),
    Output("riders-ready", "data"),
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
    """Gerencia o início e a barra de progresso da geração de entregadores.
    Ao iniciar uma nova geração, encerra imediatamente qualquer análise de raio de bar ativa.
    """
    triggered = ctx.triggered_id

    # 1. clique no botão "Gerar Entregadores": inicia o job e cancela análise de bar anterior
    if triggered == "btn-generate-riders":
        if num_riders is None or int(num_riders) <= 0:
            return (
                dash.no_update,
                dash.no_update,
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
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
            )

        start_rider_generation_job(
            system=SYSTEM,
            num_riders=int(num_riders),
            clear_existing=bool(clear_existing),
        )
        return (
            dash.no_update,
            {"type": "FeatureCollection", "features": []},
            render_nearby_search_results(None),
            dash.no_update,
            {"display": "block"},
            0,
            "0%",
            "warning",
            True,
            f"Gerando entregadores: 0 / {int(num_riders):,}".replace(",", "."),
            False,
            True,
            None,
            [],
            render_bar_details(None),
            False,
        )

    # 2. atualização periódica da barra de progresso via dcc.Interval
    state = get_rider_generation_state()
    pct = state["percent"]

    if state["running"]:
        return (
            dash.no_update,
            dash.no_update,
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
            dash.no_update,
            dash.no_update,
            dash.no_update,
            False,
        )

    # 3. geração concluída: plota todos os novos entregadores no mapa sem prender o app em análise de bar
    return (
        state["map_url"],
        {"type": "FeatureCollection", "features": []},
        render_nearby_search_results(None),
        render_riders_status(
            total_riders=state["total_riders"],
        ),
        {"display": "block"},
        100,
        "100% gerados",
        "success",
        False,
        "Entregadores gerados. Carregando os pontos no mapa…",
        True,
        False,
        dash.no_update,
        [],
        render_bar_details(None),
        bool(state["total_riders"]),
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
    app.run(debug=False, host="127.0.0.1", port=8050)
