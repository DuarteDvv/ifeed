import gzip
import csv
import osmnx as ox
from src.geo_index.geohash.geohashing import geohash_encode, geohash_decode

def read_gzip_csv(file_path):
    
    data = []
    with gzip.open(file_path, mode='rt', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)

    return data

data = read_gzip_csv('data/bares_final.csv.gz')

print(float(data[0]['latitude']), float(data[0]['longitude']))
print(float(data[1]['latitude']), float(data[1]['longitude']))
print(geohash_encode(float(data[0]['latitude']), float(data[0]['longitude']), 8))
print(geohash_encode(float(data[1]['latitude']), float(data[1]['longitude']), 8))
print(geohash_decode(geohash_encode(float(data[0]['latitude']), float(data[0]['longitude']), 8)))
print(geohash_decode(geohash_encode(float(data[1]['latitude']), float(data[1]['longitude']), 8)))
