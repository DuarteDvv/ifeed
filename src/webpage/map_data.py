"""Publica GeoJSON comprimido sem enviar ele pelas respostas de callbacks do Dash"""

import gzip
import json
import threading
from uuid import uuid4

from flask import Response

_COMPRESSED_MAPS: dict[str, bytes] = {}
_LOCK = threading.Lock()
_MAX_COMPRESSED_MAPS = 16
_FULL_MAP_ID: str | None = None
EMPTY_MAP_URL = "/_ifeed/rider-map/empty.geojson"
_EMPTY_PAYLOAD = gzip.compress(b'{"type":"FeatureCollection","features":[]}', mtime=0)


def create_map_url(geojson: dict, *, full_map: bool = False) -> str:
    "comprime o mapa uma vez e devolve a URL para o leaflet carregar"

    global _FULL_MAP_ID
    if not geojson.get("features"):
        return EMPTY_MAP_URL
    json_text = json.dumps(geojson, separators=(",", ":"), ensure_ascii=False)
    compressed_data = gzip.compress(json_text.encode("utf-8"), compresslevel=1, mtime=0)
    token = uuid4().hex
    with _LOCK:
        _COMPRESSED_MAPS[token] = compressed_data
        if full_map:
            _FULL_MAP_ID = token
        # dict preserva a ordem de inserção, então removemos primeiro as buscas mais antigas
        while len(_COMPRESSED_MAPS) > _MAX_COMPRESSED_MAPS:
            oldest = next(key for key in _COMPRESSED_MAPS if key != _FULL_MAP_ID)
            del _COMPRESSED_MAPS[oldest]
    return f"/_ifeed/rider-map/{token}.geojson"


def register_map_route(server) -> None:
    "entrega o GeoJSON comprimido pela url criada acima"
    
    @server.get("/_ifeed/rider-map/<token>.geojson")
    def rider_map_data(token: str):
        with _LOCK:
            payload = _EMPTY_PAYLOAD if token == "empty" else _COMPRESSED_MAPS.get(token)
        if payload is None:
            return Response(status=404)
        return Response(
            payload,
            mimetype="application/geo+json",
            headers={
                "Content-Encoding": "gzip",
                "Cache-Control": "private, max-age=3600, immutable",
            },
        )
