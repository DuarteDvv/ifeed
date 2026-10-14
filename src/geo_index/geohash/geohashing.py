"""Codificação e decodificação de coordenadas usando geohash."""

_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"
_BITS = (16, 8, 4, 2, 1)


def geohash_encode(latitude: float, longitude: float, size: int = 8) -> str:
    """Converte latitude e longitude em um geohash."""
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

        # cada bit escolhe a metade inferior (0) ou superior (1) do intervalo.
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
    """Converte um geohash para os limites de latitude e longitude da box delimitadora"""
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
    """converte um geohash para (latitude, longitude)"""
    latitude_bounds, longitude_bounds = geohash_decode_bounds(geohash)

    latitude = (latitude_bounds[0] + latitude_bounds[1]) / 2
    longitude = (longitude_bounds[0] + longitude_bounds[1]) / 2
    return latitude, longitude

def get_geohash_neighbors(key):
    """Retorna o centro do geohash dos 8 vizinhos do geohash fornecido. 
    - Poderia ter o caso de estarmos no limite das coordenadas, então alguns vizinhos poderiam não existir mas por 
    pelo fato de ser apenas belo horizonte isso não é um problema
    """

    prefix_6 = key[:6]

    ((lat_min, lat_max), (lon_min, lon_max)) = geohash_decode_bounds(prefix_6)
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

    return [geohash_encode(lat, lon, size=6) for lat, lon in vizinhos] 

