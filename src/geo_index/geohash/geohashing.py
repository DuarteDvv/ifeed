"""Codificação e decodificação de coordenadas usando geohash."""

_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"
_BITS = (16, 8, 4, 2, 1)


def geohash_encode(latitude: float, longitude: float, size: int = 8) -> str:
    latitude_bounds = [-90.0, 90.0]
    longitude_bounds = [-180.0, 180.0]
    characters = []
    character_value = 0
    bits_in_character = 0
    is_longitude = True

    while len(characters) < size:
        bounds = longitude_bounds if is_longitude else latitude_bounds
        coordinate = longitude if is_longitude else latitude
        midpoint = (bounds[0] + bounds[1]) / 2

        is_upper_half = coordinate > midpoint
        if is_upper_half:
            bounds[0] = midpoint
        else:
            bounds[1] = midpoint

        character_value = (character_value << 1) | int(is_upper_half)
        bits_in_character += 1
        is_longitude = not is_longitude

        if bits_in_character == 5:
            characters.append(_BASE32[character_value])
            character_value = 0
            bits_in_character = 0

    return "".join(characters)

def geohash_decode_bounds(geohash: str) -> tuple[tuple[float, float], tuple[float, float]]:
    "converte um geohash para os limites de latitude e longitude da box delimitadora"

    latitude_bounds = [-90.0, 90.0]
    longitude_bounds = [-180.0, 180.0]
    is_longitude = True

    for character in geohash:
        character_value = _BASE32.index(character)

        for mask in _BITS:
            bounds = longitude_bounds if is_longitude else latitude_bounds
            midpoint = (bounds[0] + bounds[1]) / 2

            if character_value & mask:
                bounds[0] = midpoint
            else:
                bounds[1] = midpoint

            is_longitude = not is_longitude

    return (latitude_bounds[0], latitude_bounds[1]), (longitude_bounds[0], longitude_bounds[1])

def geohash_decode(geohash: str) -> tuple[float, float]:
    "converte um geohash para coordenadas"

    latitude_bounds, longitude_bounds = geohash_decode_bounds(geohash)

    latitude = (latitude_bounds[0] + latitude_bounds[1]) / 2
    longitude = (longitude_bounds[0] + longitude_bounds[1]) / 2
    return latitude, longitude

def get_geohash_neighbors(key, size: int = 6):
    "retorna o centro do geohash dos 8 vizinhos do geohash fornecido"

    prefix = key[:size]

    ((lat_min, lat_max), (lon_min, lon_max)) = geohash_decode_bounds(prefix)
    altura_box = lat_max - lat_min
    largura_box = lon_max - lon_min

    # centro do geohash central
    lat_centro = (lat_min + lat_max) / 2
    lon_centro = (lon_min + lon_max) / 2

    # vizinhos
    vizinhos = [
        (lat_centro + altura_box, lon_centro - largura_box), # norte oeste
        (lat_centro + altura_box, lon_centro), # norte
        (lat_centro + altura_box, lon_centro + largura_box), # norte leste
        (lat_centro, lon_centro - largura_box), # oeste
        (lat_centro, lon_centro + largura_box), # leste
        (lat_centro - altura_box, lon_centro - largura_box), # sul oeste
        (lat_centro - altura_box, lon_centro), # sul
        (lat_centro - altura_box, lon_centro + largura_box) # sul leste
    ]

    return [geohash_encode(lat, lon, size=size) for lat, lon in vizinhos] 

