"""Funções e componentes de navegação no mapa e visualização de bares."""

from dash import html
import dash_bootstrap_components as dbc
import dash_leaflet as dl
import dash_leaflet.express as dlx

from preprocessing.geocodificar_bares_pbh import norm
from src.delivery_system.DeliverySystem import DeliverySystem
from src.geo_index.radix_tree.RadixTree import RadixTree
from src.geometry.geometry_utilities import squared_distance
from src.models.Bar import Bar

# Constantes geográficas e de interface
BH_CENTER = [-19.9191, -43.9386]
BH_DEFAULT_ZOOM = 12
MAX_DROPDOWN_OPTIONS = 100

# Referência à função JavaScript para customização dos clusters de bares/restaurantes
BAR_CLUSTER_TO_LAYER = {"variable": "ifeed.barClusterToLayer"}


def init_bar_catalog() -> DeliverySystem:
    """Inicializa o catálogo de bares e estruturas de entregadores do DeliverySystem."""
    system = DeliverySystem.__new__(DeliverySystem)
    system.radix_tree = RadixTree()
    system.riders = {}
    system.bars = system.load_bars()
    return system


def build_bar_indices(
    valid_bars: list[Bar],
) -> tuple[dict[int, str], dict[str, list[Bar]], dict[tuple[float, float], int], list[dict]]:
    """Gera índices em memória para busca textual, agrupamento por bairro e clique no mapa."""
    search_index: dict[int, str] = {}
    bars_by_bairro: dict[str, list[Bar]] = {}
    coords_index: dict[tuple[float, float], int] = {}

    for bar in valid_bars:
        search_index[bar.id] = norm(
            f"{bar.id} {bar.nome_fantasia} {bar.nome} {bar.bairro} {bar.endereco}"
        )
        if bar.bairro:
            bars_by_bairro.setdefault(bar.bairro, []).append(bar)
        coords_index[(round(bar.latitude, 6), round(bar.longitude, 6))] = bar.id

    bairro_options = [
        {"label": f"{bairro} ({len(lista)})", "value": bairro}
        for bairro, lista in sorted(bars_by_bairro.items())
    ]
    return search_index, bars_by_bairro, coords_index, bairro_options


def get_bar_display_name(bar: Bar) -> str:
    """Retorna o nome principal para exibição do bar."""
    if bar.nome_fantasia and bar.nome and bar.nome_fantasia != bar.nome:
        return f"{bar.nome_fantasia} ({bar.nome})"
    return bar.nome_fantasia or bar.nome or f"Bar #{bar.id}"


def format_bar_option(bar: Bar) -> dict:
    """Formata um objeto Bar como opção do dcc.Dropdown."""
    nome_curto = bar.nome_fantasia or bar.nome or f"Bar #{bar.id}"
    bairro_str = f" — {bar.bairro}" if bar.bairro else ""
    endereco_str = f" | {bar.endereco}" if bar.endereco else ""
    return {
        "label": f"[{bar.id}] {nome_curto}{bairro_str}{endereco_str}",
        "value": bar.id,
    }


def build_bars_geojson(bars: list[Bar]) -> dict:
    """Converte uma lista de objetos Bar em um FeatureCollection GeoJSON para o dash-leaflet."""
    dicts = []
    for bar in bars:
        nome_exibicao = bar.nome_fantasia or bar.nome or f"Bar #{bar.id}"
        dicts.append({
            "lat": bar.latitude,
            "lon": bar.longitude,
            "bar_id": bar.id,
            "tooltip": f"{nome_exibicao} ({bar.bairro or 'BH'})",
            "popup": (
                f"<b>{nome_exibicao}</b><br>"
                f"<small><b>ID:</b> {bar.id} | <b>Bairro:</b> {bar.bairro or 'Não informado'}</small><br>"
                f"<small><b>Endereço:</b> {bar.endereco or 'Não informado'}</small><br>"
                f"<small><b>Geohash:</b> {bar.geohash}</small>"
            ),
        })
    return dlx.dicts_to_geojson(dicts)


def find_bar_from_click(
    click_data: dict | None,
    system: DeliverySystem,
    coords_index: dict[tuple[float, float], int],
    valid_bars: list[Bar],
) -> Bar | None:
    """Identifica o Bar clicado no mapa a partir do clickData do dl.GeoJSON."""
    if not click_data:
        return None

    # 1. Tenta obter propriedades da Feature GeoJSON
    props = click_data.get("properties") or {}
    if props.get("cluster"):
        return None
    if "bar_id" in props:
        return system.get_bar(int(props["bar_id"]))

    # 2. Tenta pelo ID direto da Feature
    direct_id = click_data.get("id")
    if direct_id is not None and str(direct_id).isdigit():
        bar = system.get_bar(int(direct_id))
        if bar:
            return bar

    # 3. Tenta extrair coordenadas (GeoJSON geometry [lon, lat] ou latlng)
    lat, lon = None, None
    geometry = click_data.get("geometry") or {}
    coords = geometry.get("coordinates")
    if isinstance(coords, (list, tuple)) and len(coords) >= 2:
        lon, lat = coords[0], coords[1]
    else:
        latlng = click_data.get("latlng")
        if isinstance(latlng, dict):
            lat, lon = latlng.get("lat"), latlng.get("lng")
        elif isinstance(latlng, (list, tuple)) and len(latlng) >= 2:
            lat, lon = latlng[0], latlng[1]

    if lat is None or lon is None:
        return None

    # Tentativa exata por coordenada arredondada
    exact_id = coords_index.get((round(float(lat), 6), round(float(lon), 6)))
    if exact_id is not None:
        return system.get_bar(exact_id)

    # Fallback usando squared_distance do módulo de geometria do projeto
    target = (float(lat), float(lon))
    closest_bar = min(
        valid_bars,
        key=lambda b: squared_distance((b.latitude, b.longitude), target),
    )
    if squared_distance((closest_bar.latitude, closest_bar.longitude), target) <= 1e-8:
        return closest_bar

    return None


def render_bar_details(bar: Bar | None) -> dbc.Card:
    """Renderiza o card lateral com as informações do bar selecionado."""
    if bar is None:
        return dbc.Card(
            dbc.CardBody([
                html.H6("Nenhum bar selecionado", className="text-muted mb-2"),
                html.P(
                    "Utilize a caixa de busca acima para procurar um bar por nome, "
                    "nome fantasia, endereço, bairro ou ID, ou clique diretamente em "
                    "um marcador no mapa.",
                    className="small text-secondary mb-0",
                ),
            ]),
            className="bg-light border-0 shadow-sm",
        )

    nome_principal = bar.nome_fantasia or bar.nome or f"Bar #{bar.id}"
    mostrar_razao_social = bool(
        bar.nome and bar.nome_fantasia and bar.nome != bar.nome_fantasia
    )

    return dbc.Card(
        dbc.CardBody([
            dbc.Badge(f"ID #{bar.id}", color="danger", className="mb-2"),
            html.H5(nome_principal, className="card-title fw-bold mb-1"),
            html.P(
                bar.nome,
                className="text-muted small mb-2",
                style={"display": "block" if mostrar_razao_social else "none"},
            ),
            html.Hr(className="my-2"),
            html.Div([
                html.Strong("Bairro: "),
                html.Span(bar.bairro or "Não informado"),
            ], className="small mb-1"),
            html.Div([
                html.Strong("Endereço: "),
                html.Span(bar.endereco or "Não informado"),
            ], className="small mb-1"),
            html.Div([
                html.Strong("Coordenadas: "),
                html.Code(f"({bar.latitude:.6f}, {bar.longitude:.6f})"),
            ], className="small mb-1"),
            html.Div([
                html.Strong("Geohash (nível 8): "),
                dbc.Badge(bar.geohash or "N/A", color="secondary", className="font-monospace"),
            ], className="small"),
        ]),
        className="border-danger shadow-sm",
    )


def get_zoom_for_radius(radius_km: float | None) -> int:
    """Retorna um nível de zoom adequado para enquadrar o raio de atendimento no mapa."""
    if radius_km is None or radius_km <= 0:
        return 16
    if radius_km <= 0.4:
        return 16
    if radius_km <= 1.0:
        return 15
    if radius_km <= 2.5:
        return 14
    if radius_km <= 5.0:
        return 13
    return 12


def render_highlighted_bar_layer(
    bar: Bar | None,
    radius_meters: float | None = None,
) -> list:
    """Cria a camada de destaque no mapa para o bar selecionado e seu raio de atendimento."""
    if bar is None or bar.latitude is None or bar.longitude is None:
        return []

    nome_exibicao = get_bar_display_name(bar)
    position = [bar.latitude, bar.longitude]
    layers = []

    if radius_meters is not None and radius_meters > 0:
        layers.append(
            dl.Circle(
                center=position,
                radius=float(radius_meters),
                color="#ff6b00",
                weight=2,
                fillColor="#ff6b00",
                fillOpacity=0.08,
                dashArray="6, 6",
                interactive=False,
            )
        )

    layers.extend([
        # Halo pulsante de destaque ao redor do bar selecionado
        dl.CircleMarker(
            center=position,
            radius=18,
            color="#d9534f",
            fillColor="#d9534f",
            fillOpacity=0.25,
            weight=3,
        ),
        # Ponto central destacado
        dl.CircleMarker(
            center=position,
            radius=8,
            color="#ffffff",
            fillColor="#d9534f",
            fillOpacity=1.0,
            weight=2,
            children=[
                dl.Tooltip(
                    f"📍 {nome_exibicao}",
                    permanent=True,
                    direction="top",
                    offset=[0, -10],
                ),
                dl.Popup([
                    html.B(nome_exibicao),
                    html.Br(),
                    html.Small(f"ID: {bar.id} | Bairro: {bar.bairro or 'Não informado'}"),
                    html.Br(),
                    html.Small(bar.endereco or "Endereço não informado"),
                ]),
            ],
        ),
    ])
    return layers


def filter_bar_options(
    search_value: str | None,
    candidate_bars: list[Bar],
    search_index: dict[int, str],
    max_options: int = MAX_DROPDOWN_OPTIONS,
    current_value: int | None = None,
    system: DeliverySystem | None = None,
) -> list[dict]:
    """Filtra as opções de bares com base na consulta e garante que o bar selecionado esteja presente."""
    query = norm(search_value) if search_value else ""

    if not query:
        matched = candidate_bars[:max_options]
    else:
        exact_or_prefix = []
        contains = []
        for bar in candidate_bars:
            if str(bar.id) == query or norm(bar.nome_fantasia or bar.nome).startswith(query):
                exact_or_prefix.append(bar)
            elif query in search_index.get(bar.id, ""):
                contains.append(bar)
            if len(exact_or_prefix) >= max_options:
                break
        matched = (exact_or_prefix + contains)[:max_options]

    options = [format_bar_option(bar) for bar in matched]

    if current_value is not None and system is not None:
        selected_bar = system.get_bar(int(current_value))
        if selected_bar and all(opt["value"] != selected_bar.id for opt in options):
            options.insert(0, format_bar_option(selected_bar))

    return options

