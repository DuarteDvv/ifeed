class KDTreeNode:

    def __init__(self, coords, axis, left=None, right=None):
        self.coords = coords
        self.axis = axis        # eixo de divisão nesse nível

        self.left = left        # subárvore com valores menores no eixo atual
        self.right = right      # subárvore com valores maiores no eixo atual