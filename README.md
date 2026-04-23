# Scraper Projetos Ativos UFG

Pipeline simples para coletar projetos ativos no portal da FUNAPE, gerar um CSV consolidado e publicar uma interface web para exploração por cards, órgão parceiro, tipo e área.

## O que este repositório faz

1. Lê o `link.txt` com a URL base do portal e as regras de coleta.
2. Consulta a API pública usada pelo frontend da FUNAPE.
3. Filtra dois grupos de projetos:
   - CEIA com status `Ativo`
   - Instituto de Informática com status `Ativo` e modalidade `P&D e Inovação` ou `Pesquisa`
4. Gera um CSV com dados da listagem e do detalhe de cada projeto.
5. Classifica os projetos por `tipo` e `área`.
6. Gera um catálogo web estático com busca e filtros.

## Estrutura

```text
.
├── build_project_catalog.py
├── ceia_projetos_nao_encerrados.csv
├── link.txt
├── scrape_ceia_projetos.py
└── web
    ├── app.js
    ├── data
    │   └── projects.json
    ├── index.html
    └── styles.css
```

## Requisitos

- Python 3.10+
- Acesso à internet para consultar a API da FUNAPE

Os scripts Python usam apenas a biblioteca padrão.

## Como gerar os dados

### 1. Coletar os projetos ativos do catálogo

```bash
python scrape_ceia_projetos.py
```

Saída principal:

- `ceia_projetos_nao_encerrados.csv`

### 2. Gerar o catálogo classificado para a interface

```bash
python build_project_catalog.py
```

Saída principal:

- `web/data/projects.json`

## Como abrir a interface web

```bash
python -m http.server 4173
```

Depois acesse:

```text
http://127.0.0.1:4173/web/
```

## Critérios de classificação

### Tipo

O campo `tipo` é derivado principalmente de:

- `lista_modalidade`
- `lista_forma_contratacao`
- alguns termos do título, quando indicam capacitação

Categorias atuais:

- `P&D e Inovação`
- `Pesquisa Aplicada`
- `Capacitação e Formação`
- `Desenvolvimento Científico`

### Área

O campo `área` não existe na origem. Ele é inferido por regras de palavras-chave no título do projeto em `build_project_catalog.py`.

Categorias atuais:

- `IA Generativa e Conversacional`
- `Educação e Capacitação`
- `Logística e Supply Chain`
- `Saúde`
- `Mobilidade e Veículos`
- `Finanças, Marketing e Negócios`
- `Jurídico`
- `Software e Desenvolvimento`
- `Energia`
- `Gestão e Governança`
- `Visão Computacional`
- `Agro e Alimentos`
- `Construção e BIM`
- `Segurança e Monitoramento`

Se quiser refinar a taxonomia, altere a lista `AREA_RULES` em `build_project_catalog.py`.

## Observações

- O arquivo `web/data/projects.json` é gerado a partir do CSV e está versionado para facilitar a publicação da interface estática.
- O catálogo mostra os cards com duas informações principais:
  - descrição do projeto
  - responsável
- O catálogo agora também permite filtrar por `órgão parceiro`.
- O modal do card exibe metadados adicionais sem poluir a leitura da grade principal.
