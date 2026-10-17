"""implementação de kd-tree para busca espacial do vizinho mais próximo."""

import heapq
import math

from src.generation.kd_tree.Node import KDTreeNode
from src.geometry.geometry_utilities import (
    get_axis_coord,
    split_points_by_median,
    squared_distance,
    unpack_point,
)

__all__ = [
    "KDTree",
    "squared_distance",
    "split_points_by_median",
    "unpack_point",
    "get_axis_coord",
]


class KDTree:

    def __init__(self, points=None, k=2):
        self.k = k
        self.root = self.build_kdtree(points) if points else None


    def build_kdtree(self, points, depth=0):
        if not points:
            return None

        axis = depth % self.k
        left_points, median_item, right_points = split_points_by_median(points, axis)

        coords, data = unpack_point(median_item)
        left_child = self.build_kdtree(left_points, depth + 1)
        right_child = self.build_kdtree(right_points, depth + 1)

        return KDTreeNode(
            coords=coords,
            axis=axis,
            left=left_child,
            right=right_child,
            data=data,
        )


    def insert(self, point, data=None):
        coords, item_data = unpack_point(point)
        if data is not None:
            item_data = data

        self.root = self._insert_node(self.root, coords, item_data, depth=0)

    
    def _insert_node(self, current, coords, data, depth):
        "percorre a árvore recursivamente até encontrar a posição correta para o novo nó"

        if current is None:
            axis = depth % self.k
            return KDTreeNode(coords=coords, axis=axis, data=data)

        axis = current.axis
        if coords[axis] < current.coords[axis]:
            current.left = self._insert_node(current.left, coords, data, depth + 1)
        else:
            current.right = self._insert_node(current.right, coords, data, depth + 1)

        return current


    def find_nearest(self, target):
        if self.root is None:
            return None, float("inf")

        target_coords, _ = unpack_point(target)

        best = {"node": None, "dist_sq": float("inf")}
        self._search_nearest(self.root, target_coords, best)

        if best["node"] is None:
            return None, float("inf")

        return best["node"], math.sqrt(best["dist_sq"])

    
    def nearest(self, target):
        "método de conveniência que retorna apenas o nó mais próximo do alvo, sem a distância"

        node, _ = self.find_nearest(target)
        return node


    def _search_nearest(self, current, target_coords, best):
        "realiza a busca recursiva do vizinho mais próximo com poda de ramos distantes"

        if current is None:
            return

        # calcula a distância do nó atual até o alvo
        dist_sq = squared_distance(current.coords, target_coords)
        if dist_sq < best["dist_sq"]:
            best["node"] = current
            best["dist_sq"] = dist_sq

        axis = current.axis
        target_val = target_coords[axis]
        current_val = current.coords[axis]

        # explora primeiro o ramo mais próximo do alvo
        if target_val < current_val:
            first, second = current.left, current.right
        else:
            first, second = current.right, current.left

        self._search_nearest(first, target_coords, best)

        # verifica se o outro lado pode conter ponto mais próximo
        diff = target_val - current_val
        if (diff * diff) < best["dist_sq"]:
            self._search_nearest(second, target_coords, best)


    def find_k_nearest(self, target, k=1):
        if self.root is None or k <= 0:
            return []

        target_coords, _ = unpack_point(target)
        heap = []
        self._search_k_nearest(self.root, target_coords, k, heap)

        results = []
        for neg_dist_sq, _, node in sorted(heap, key=lambda item: -item[0]):
            results.append((node, math.sqrt(-neg_dist_sq)))
        return results


    def _search_k_nearest(self, current, target_coords, k, heap):
        "realiza a busca recursiva dos k vizinhos usando fila de prioridade para poda"

        if current is None:
            return

        dist_sq = squared_distance(current.coords, target_coords)
        if len(heap) < k:
            heapq.heappush(heap, (-dist_sq, id(current), current))
        elif dist_sq < -heap[0][0]:
            heapq.heapreplace(heap, (-dist_sq, id(current), current))

        axis = current.axis
        target_val = target_coords[axis]
        current_val = current.coords[axis]

        if target_val < current_val:
            first, second = current.left, current.right
        else:
            first, second = current.right, current.left

        self._search_k_nearest(first, target_coords, k, heap)

        diff = target_val - current_val
        worst_dist_sq = -heap[0][0] if len(heap) == k else float("inf")
        if (diff * diff) < worst_dist_sq:
            self._search_k_nearest(second, target_coords, k, heap)