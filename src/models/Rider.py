"""Classe que representa um entregador no sistema de entrega"""

class Rider:
    def __init__(self, id, latitude, longitude, geohash=None):
        self.id = id
        self.latitude = latitude
        self.longitude = longitude
        self.geohash = geohash  