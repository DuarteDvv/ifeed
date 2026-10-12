import gzip
import csv
import osmnx as ox
import requests

def read_gzip_csv(file_path):
    
    data = []
    with gzip.open(file_path, mode='rt', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)

    return data

data = read_gzip_csv('data/bares_final.csv.gz')

print(data[0])