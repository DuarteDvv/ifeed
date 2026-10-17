class KDTreeNode:

    # inicializa o nó com coordenadas, eixo de divisão, filhos e dados opcionais
    def __init__(self, coords, axis, left=None, right=None, data=None):
        self.coords = coords
        self.axis = axis        # eixo de divisão nesse nível
        self.left = left        # subárvore com valores menores no eixo atual
        self.right = right      # subárvore com valores maiores no eixo atual
        self.data = data        # dado opcional associado ao ponto

    # indica se o nó é uma folha, ou seja, não possui filhos
    def is_leaf(self):
        return self.left is None and self.right is None