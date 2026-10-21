"""Nó da arvore radix
(Ao invés de criar 2 tipos de nós (nós internos e nós folhas), por simplicidade todos os nós são do mesmo tipo, mas apenas os nós folhas 
possuem ids e isso gasta um pouco mais de memória por causa dos ponteiros de lista vazia)
"""

class RadixTreeNode:
    def __init__(self, ids=None, segment=None):
        self.ids = ids if ids is not None else [] # ids dos motoristas (vazio se o nó não for uma folha)
        self.segment = segment # segmento compacto do nó (None se for a raiz)
        self.children = {} # dicionário de filhos, onde a chave é o primeiro caractere do segmento do filho e o valor é o nó filho correspondente

    def add_child(self, child_node):
        self.children[child_node.segment[0]] = child_node

    def get_child(self, char):
        return self.children.get(char)

    def remove_child(self, char):
        if char in self.children:
            del self.children[char]

    def is_leaf(self):
        return len(self.children) == 0

        