"""Classe que representa um bar, com seus atributos"""

class Bar:
    def __init__(self, id, nome, nome_fantasia, endereco, bairro, latitude, longitude):
        self.id = id
        self.nome = nome
        self.nome_fantasia = nome_fantasia
        self.endereco = endereco
        self.bairro = bairro
        self.latitude = latitude
        self.longitude = longitude
        self.geohash = None
        

