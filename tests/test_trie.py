"""Execute na raiz do projeto: python3 tests/test_trie.py"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.geo_index.radix_tree.RadixTree import RadixTree


print("Teste 1 - Inserir e buscar uma chave completa")
tree = RadixTree()
tree.insert("7h2ybb5z", 101)
print("Entrada: insert('7h2ybb5z', 101); search_prefix('7h2ybb5z')")
print("Saída esperada:", [101])
print("Saída obtida:", tree.search_prefix("7h2ybb5z"))

print("\nTeste 2 - Prefixo que termina no meio de um segmento")
tree = RadixTree()
tree.insert("7h2ybb5z", 101)
print("Entrada: insert('7h2ybb5z', 101); search_prefix('7h2')")
print("Saída esperada:", [101])
print("Saída obtida:", tree.search_prefix("7h2"))

print("\nTeste 3 - Várias chaves com um prefixo comum")
tree = RadixTree()
tree.insert("7h2ybb5z", 101)
tree.insert("7h2ybc1a", 102)
tree.insert("7h2yb8k", 103)
tree.insert("7h2xpesh", 104)
print("Entrada: chaves 7h2ybb5z (101), 7h2ybc1a (102), 7h2yb8k (103), 7h2xpesh (104)")
print("Busca: search_prefix('7h2yb')")
print("Saída esperada:", [101, 102, 103])
print("Saída obtida:", tree.search_prefix("7h2yb"))

print("\nTeste 4 - Dois IDs na mesma chave")
tree = RadixTree()
tree.insert("7h2ybb5z", 101)
tree.insert("7h2ybb5z", 102)
print("Entrada: insert('7h2ybb5z', 101); insert('7h2ybb5z', 102); search_prefix('7h2ybb5z')")
print("Saída esperada:", [101, 102])
print("Saída obtida:", tree.search_prefix("7h2ybb5z"))

print("\nTeste 5 - Prefixo inexistente")
tree = RadixTree()
tree.insert("7h2ybb5z", 101)
print("Entrada: insert('7h2ybb5z', 101); search_prefix('7h2yba')")
print("Saída esperada:", [])
print("Saída obtida:", tree.search_prefix("7h2yba"))
