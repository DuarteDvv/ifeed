# iFeed

Mapa de bares e entregadores de Belo Horizonte.

## Como executar

Pré-requisito: ter o `uv` instalado. Ele prepara o ambiente com Python 3.12 e as dependências.

1. Abra o terminal na pasta do projeto:

   ```bash
   cd ifeed
   ```

2. Instale as dependências:

   ```bash
   uv sync
   ```

3. Inicie o aplicativo:

   ```bash
   uv run main.py
   ```

4. Abra **http://127.0.0.1:8050** no navegador.

Aguarde o carregamento da malha viária. Na seção **Entregadores**, informe a quantidade e clique em **Gerar Entregadores**. Depois, selecione um bar no mapa ou na busca.

