#!/usr/bin/env python3
"""Geocodificação dos bares usando o cadastro de endereços da PBH (https://dados.pbh.gov.br/dataset/endereco-cadastro-tecnico-municipal/resource/74dbdfce-52b4-452c-b16c-d1737191084b)

Casos de retorno de pontos por endereco:
- Correspondência única: coordenada exata
- múltiplos pontos: mediana geométrica das coordenadas retornadas
- nenhuma: nulo

Uso: python3 preprocessing/geocodificar_bares_pbh.py --bares data/bares.csv.gz --pbh data/enderecos_pbh.csv.gz --saida data/bares_final.csv
Também tivemos que converter as coordenadas do cadastro da PBH de EPSG:31983 para EPSG:4326 (WGS84) (usada no geohash) usando o pyproj.
"""
import argparse
import re
import unicodedata
from collections import defaultdict
import pandas as pd
from pyproj import Transformer

from src.geometry.geometry_utilities import median_geometric

ALIASES = {"AVE": "AVENIDA", "AV": "AVENIDA", "R": "RUA", "PCA": "PRACA", "PRA": "PRACA", "PC": "PRACA", "ROD": "RODOVIA", "AL": "ALAMEDA", "TRV": "TRAVESSA", "TV": "TRAVESSA", "EST": "ESTRADA"}

def norm(value):
    if pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii").upper()
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9]+", " ", text)).strip()

def tipo(value):
    s = norm(value)
    return ALIASES.get(s, s)

def numero(value):
    s = norm(value)
    if re.fullmatch(r"\d+", s):
        return str(int(s))
    return s

def parse_geom(value):
    if not isinstance(value, str):
        return None
    m = re.match(r"^POINT\s*\(\s*([-+\d.eE]+)\s+([-+\d.eE]+)\s*\)$", value.strip(), re.I)
    if not m:
        return None
    return (float(m.group(1)), float(m.group(2)))

def preparar_pbh(df):
    df = df.copy()
    df["t"] = df["DESC_TIPO_LOGRADOURO"].map(tipo)
    df["r"] = df["NOME_LOGRADOURO"].map(norm)
    df["n"] = df["NUMERO_IMOVEL"].map(numero)
    df["bp"] = df["NOME_BAIRRO_POPULAR"].map(norm)
    df["bo"] = df["NOME_BAIRRO_OFICIAL"].map(norm)
    df["xy"] = df["GEOMETRIA"].map(parse_geom)
    df = df[df["xy"].notna() & df["r"].ne("") & df["n"].ne("")]
    by_popular, by_oficial, by_rua = defaultdict(set), defaultdict(set), defaultdict(set)
    for t, r, n, bp, bo, xy in df[["t", "r", "n", "bp", "bo", "xy"]].itertuples(index=False, name=None):
        if bp:
            by_popular[(t,r,n,bp)].add(xy)
        if bo:
            by_oficial[(t,r,n,bo)].add(xy)
        by_rua[(t,r,n)].add(xy)
    return by_popular, by_oficial, by_rua

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bares", default="bares.csv.gz")
    parser.add_argument("--pbh", required=True)
    parser.add_argument("--saida", default="bares_geocodificados.csv")
    args = parser.parse_args()

    print("Lendo arquivos...")
    bares = pd.read_csv(args.bares, dtype=str, encoding="utf-8-sig", compression="infer", keep_default_na=False)
    pbh = pd.read_csv(args.pbh, dtype=str, encoding="utf-8-sig", keep_default_na=False, compression="infer", low_memory=False,
                      usecols=["DESC_TIPO_LOGRADOURO", "NOME_LOGRADOURO", "NUMERO_IMOVEL", "NOME_BAIRRO_POPULAR", "NOME_BAIRRO_OFICIAL", "GEOMETRIA"])
    indexes = preparar_pbh(pbh)
    print("Índices PBH preparados.")
    transform = Transformer.from_crs("EPSG:31983", "EPSG:4326", always_xy=True)
    results = []
    for row in bares.itertuples(index=False):
        obj = dict(zip(bares.columns, row))
        k3 = (tipo(obj["DESC_LOGRADOURO"]), norm(obj["NOME_LOGRADOURO"]), numero(obj["NUMERO_IMOVEL"]))
        bairro = norm(obj["NOME_BAIRRO"])
        options = None
        for candidates in (indexes[0].get(k3+(bairro,)), indexes[1].get(k3+(bairro,))):
            if candidates:
                options = candidates
                break
        if not options:
            fallback = indexes[2].get(k3, set())
            if len(fallback) == 1:
                options = fallback
        record = dict(obj)
        record.update(latitude="", longitude="", PRECISAO_COORD="nao_encontrado")
        if options:
            points = sorted(options)
            xy = median_geometric(points)
            lon, lat = transform.transform(float(xy[0]), float(xy[1]))
            record.update(latitude=lat, longitude=lon, PRECISAO_COORD="exato_cadastral" if len(points)==1 else "aproximado_mediana")
        results.append(record)
    print("PBH:", pd.Series([r["PRECISAO_COORD"] for r in results]).value_counts().to_dict())

    final = pd.DataFrame(results)
    final.to_csv(args.saida, index=False, encoding="utf-8-sig", compression="gzip")
    print("Resumo final:", final["PRECISAO_COORD"].value_counts().to_dict())
    print("Arquivo:", args.saida)

if __name__ == "__main__":
    main()
