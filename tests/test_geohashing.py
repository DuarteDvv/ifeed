"""Execute na raiz do projeto: python3 tests/test_geohashing.py"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.geo_index.geohash.geohashing import (
    geohash_decode,
    geohash_decode_bounds,
    geohash_encode,
    get_geohash_neighbors,
)


print("Teste 1 - geohash_encode")
print("Entrada: latitude=42.6, longitude=-5.6, size=5")
print("Saída esperada: ezs42")
print("Saída obtida:", geohash_encode(42.6, -5.6, size=5))

print("\nTeste 2 - geohash_encode")
print("Entrada: latitude=57.64911, longitude=10.40744, size=8")
print("Saída esperada: u4pruydq")
print("Saída obtida:", geohash_encode(57.64911, 10.40744, size=8))

print("\nTeste 3 - geohash_decode_bounds")
print("Entrada: ezs42")
print("Saída esperada:", ((42.5830078125, 42.626953125), (-5.625, -5.5810546875)))
print("Saída obtida:", geohash_decode_bounds("ezs42"))

print("\nTeste 4 - geohash_decode")
print("Entrada: ezs42")
print("Saída esperada:", (42.60498046875, -5.60302734375))
print("Saída obtida:", geohash_decode("ezs42"))

print("\nTeste 5 - get_geohash_neighbors")
print("Entrada: 7h2ybb5z")
print("Saída esperada:", ["7h2yb9", "7h2ybc", "7h2yc1", "7h2yb8", "7h2yc0", "7h2y8x", "7h2y8z", "7h2y9p"])
print("Saída obtida:", get_geohash_neighbors("7h2ybb5z"))
