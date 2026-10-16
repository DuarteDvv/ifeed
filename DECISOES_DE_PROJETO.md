# Decisões de projeto do iFeed

## 1. Pré-processamento das coordenadas

- **Fonte:** [cadastro de endereços da PBH](https://dados.pbh.gov.br/dataset/endereco-cadastro-tecnico-municipal/resource/74dbdfce-52b4-452c-b16c-d1737191084b), cruzado localmente com os endereços dos bares.
- Normalizar acentos, maiúsculas, pontuação, espaços, abreviações de logradouros e números de imóveis.
- Extrair pontos de `POINT(x y)`; desconsiderar registros municipais sem geometria, rua ou número válidos.
- Criar índices com `defaultdict(set)`: endereços como chaves e conjuntos de coordenadas para remover duplicatas.
- Buscar por tipo de logradouro, rua, número e bairro; priorizar bairro popular e depois bairro oficial.
- Sem correspondência por bairro, aceitar rua e número somente quando houver uma única coordenada possível.
- **Correspondência única:** usar a coordenada cadastral e registrar `exato_cadastral`.
- **Ambiguidade:** calcular a mediana geométrica por Weiszfeld, em metros, evitando escolher arbitrariamente um ponto; registrar `aproximado_mediana`.
- **Sem correspondência segura:** preservar o estabelecimento com coordenadas vazias e registrar `nao_encontrado`.
- Converter `EPSG:31983` para latitude/longitude em `EPSG:4326` com `pyproj`, compatível com Geohash e mapas.
- Salvar coordenadas e precisão da localização em `data/bares_final.csv.gz`.

## 2. Pré-processamento do grafo de BH

- Obter a malha do OpenStreetMap com `graph_from_place("Belo Horizonte, Minas Gerais, Brazil", network_type="drive", simplify=True)`.
- Usar vias para veículos e simplificar vértices intermediários, preservando a geometria das ruas.
- Manter o grafo dirigido e suas arestas paralelas, respeitando mãos únicas e alternativas de percurso.
- Adicionar `speed_kph` e `travel_time` com o [OSMnx](https://osmnx.readthedocs.io/en/stable/user-reference.html#osmnx.routing.add_edge_travel_times); estimar tempos pelas velocidades, sem dados de trânsito ao vivo.
- Salvar o grafo e seus atributos em `data/malha_viaria_bh.graphml`.
- Reutilizar o arquivo local: evitar espera por downloads, dependência da internet e mudanças dos dados entre execuções.
- Manter cache das respostas em `data/.osmnx_cache`; gravar um arquivo temporário antes de substituir o GraphML final.

## 3. Geohashing e armazenamento

- Implementar a codificação diretamente no projeto, subdividindo os intervalos de latitude e longitude.
- Começar pela longitude e alternar os eixos; representar a metade inferior por `0` e a superior por `1`.
- Acumular bits com deslocamentos binários e transformar cada grupo de cinco bits em um caractere Base32.
- Definir **8 caracteres** para os geohashes dos restaurantes e dos riders.
- Decodificar os limites da célula e calcular seu centro; preservar as coordenadas originais, pois o centro é uma aproximação.
- Calcular o hash do restaurante no carregamento e guardar em `Bar.geohash`, evitando recálculos durante consultas.
- Manter `geohash=None` quando o restaurante não tiver coordenadas.
- **Planejado para os riders:** calcular e armazenar o hash após ajustar a posição à rua; atualizar hash e índice quando a posição mudar.

## 4. Trie compacta e recuperação dos IDs

- Usar uma árvore radix: comprimir sequências comuns em segmentos para reduzir a quantidade de nós.
- Usar uma raiz vazia e uma única classe de nó, simplificando nós internos e folhas.
- Guardar em cada nó um segmento de string, uma lista de IDs e um dicionário de filhos.
- Indexar os filhos pelo primeiro caractere do segmento, com acesso médio em `O(1)`.
- Guardar IDs nas folhas; permitir vários entregadores no mesmo geohash usando uma lista.
- Acrescentar `$` à chave para marcar seu término, sem conflitar com o alfabeto Base32.
- Dividir segmentos pelo maior prefixo comum quando uma inserção encontrar divergência.
- Percorrer somente ramos compatíveis na busca; aceitar prefixos que terminem no meio de um segmento.
- Coletar os IDs de subárvores recursivamente, unindo as listas das folhas com `extend`.
- Coletar sob demanda, evitando cópias dos IDs de toda a subárvore em cada nó interno.
- Usar dicionários `ID -> Rider` e `ID -> Bar` para recuperar rapidamente os objetos após a busca.

## 5. Vizinhos e precisão 6

- Armazenar hashes com 8 caracteres e consultar a trie com os **6 primeiros caracteres**.
- Usar precisão 6 como aproximação operacional de vizinhança urbana: em BH, uma célula mede aproximadamente **1,15 km × 0,61 km**.
- Tratar “escala de bairro” como aproximação; células de Geohash não seguem limites administrativos nem comprovam o tamanho médio dos bairros.
- Decodificar a célula do bar para obter centro, altura e largura.
- Deslocar o centro nas oito direções e codificar os centros vizinhos com precisão 6.
- Consultar a célula central e as oito vizinhas para cobrir as bordas; eliminar IDs repetidos com `dict.fromkeys`.
- Manter a pré-seleção independente do raio, assumindo um raio menor que a menor dimensão da célula.

## 6. Busca no sistema e rotas

- Em `search_nearby`, selecionar o bar por ID, consultar a trie e recuperar os riders pelo dicionário.
- Retornar `None` para bar inexistente ou sem coordenadas; `[]` para consulta válida sem candidatos.
- Classificar pelo raio em **metros**, usando Haversine com `ox.distance.great_circle`; o recorte regional vem do Geohash.
- Preservar candidatos fora do raio com `within_range=False`, permitindo sua futura exibição em cinza.
- Associar as coordenadas aos nós mais próximos com `nearest_nodes`; usar `scikit-learn`, exigido pelo OSMnx para esse grafo geográfico.
- Calcular rotas no sentido **entregador → bar**, respeitando a direção das ruas.
- Usar `shortest_path(weight="travel_time")` para priorizar a chegada mais rápida.
- Extrair distância e tempo da **mesma rota**, usando `route_to_gdf(weight="travel_time")` também para escolher arestas paralelas.
- Retornar `distance` e `road_distance` em metros; converter segundos para `estimated_time` em **minutos**.
- Sem rota, retornar distância viária e tempo como `None`; para origem e destino no mesmo nó, retornar zero.
- Consultar nós e calcular rotas em lote, reduzindo reconstruções de índices e validações repetidas do grafo.
- Medição local com 40 candidatos: aproximadamente **8,95 s → 0,45 s**, preservando os resultados.

## 7. Verificação das partes

- Separar exemplos de Geohash, trie, busca espacial e `DeliverySystem` em arquivos próprios.
- Usar Python e prints de entrada, saída esperada e saída obtida, sem framework de testes.
- Combinar exemplos controlados com CSV e grafo reais, inserindo riders artificiais em nós das ruas.
