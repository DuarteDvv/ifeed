""" Implementação de uma árvore radix (ou trie compacta) para armazenar chaves (geohashes) e seus respectivos IDs
"""
from src.geo_index.radix_tree.Node import RadixTreeNode

class RadixTree:
    def __init__(self):
        self.root = RadixTreeNode()

    def _common_prefix(self, str1, str2):
        """retorna o prefixo comum mais longo entre duas strings"""

        min_length = min(len(str1), len(str2))
        for i in range(min_length):
            if str1[i] != str2[i]:
                return str1[:i]
        return str1[:min_length]


    def insert(self, key, id):
        """Insere uma chave (geohash) e seu ID na árvore radix"""

        key = key + "$" # simbolo fora do vocabulário que indica o final da chave

        current_node = self.root
        while True:

            first_char = key[0]
            child_node = current_node.get_child(first_char)

            if child_node is None:
                # nenhum filho com o primeiro caractere da chave, então criamos um novo nó folha

                new_node = RadixTreeNode(ids=[id], segment=key)
                current_node.add_child(new_node)
                return


            longest_common_prefix = self._common_prefix(key, child_node.segment)
            size_of_common_prefix = len(longest_common_prefix)
            size_of_child_segment = len(child_node.segment)

            if size_of_common_prefix == size_of_child_segment:
                # o segmento inyteiro do filho é um prefixo da chave, então continuamos a busca no filho

                key = key[size_of_common_prefix:]
                current_node = child_node

                if len(key) == 0:
                    # estamos no nó folha correspondente à chave, então adicionamos o ID à lista de IDs do nó folha
                    child_node.ids.append(id)
                    return
            else:
                # apenas um pedaco do segmento do filho é prefixo da chave, então precisamos dividir o nó filho em um nó intermediário compartilhado com 2 ramos
                new_intermediate_node = RadixTreeNode(segment=longest_common_prefix)

                # substitui o filho antigo pelo nó intermediário no pai
                current_node.remove_child(first_char)

                # segmento do nó filho é apenas a parte que diverge
                child_node.segment = child_node.segment[size_of_common_prefix:]

                # nó filho com restante do segmento do filho original vira filho do nó intermediário (ramo 1)
                new_intermediate_node.add_child(child_node)

                # nó intermediário vira filhoo do nó atual
                current_node.add_child(new_intermediate_node)

                # novo nó folha para parte restante da chave (ramo 2)
                new_leaf_node = RadixTreeNode(ids=[id], segment=key[size_of_common_prefix:])
                new_intermediate_node.add_child(new_leaf_node)

                return

    def _collect_ids(self, node):
        """Retorna os IDs armazenados nas folhas abaixo do nó."""

        ids = list(node.ids)
        for child_node in node.children.values():
            ids.extend(self._collect_ids(child_node)) # junta os IDs das folhas abaixo do nó filho
        return ids

    def search_prefix(self, key):
        """Buscar IDs de um prefixo especifico, ou seja, subarvores"""

        if key is None or key == "":
            return None

        current_node = self.root
        while key:
            child_node = current_node.get_child(key[0])

            if child_node is None:
                return []

            longest_common_prefix = self._common_prefix(key, child_node.segment)
            common_prefix_size = len(longest_common_prefix)
            size_of_child_segment = len(child_node.segment)

            if common_prefix_size == len(key):
                # achou o prefixo inteiro
                return self._collect_ids(child_node)

            if common_prefix_size < size_of_child_segment:
                # o prefixo não existe na arvore
                return []

            # prefixo comum == segmento do child, ou seja, consumimos ele e vamos para o proximo
            key = key[common_prefix_size:]
            current_node = child_node

        return self._collect_ids(current_node)

    




   

    

