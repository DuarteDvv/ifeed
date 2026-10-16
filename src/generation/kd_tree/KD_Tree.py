"""Implementação de uma KD-Tree para fazer a busca heurística pela rua mais próxima de um entregador
(usando segmentos das ruas como as arestas)
"""

from src.generation.kd_tree.Node import KDTreeNode

class KDTree:

    def __init__(self, points):
        self.root = None

    def build_kdtree(self, points, depth=0):
        axis = depth % 2
        median_idx = points