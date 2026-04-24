# AplicAI — Catálogo + Match com IA

Plataforma para alunos da UFG explorarem projetos ativos do **CEIA**, **Instituto de Informática** e **AKCIT**, descobrirem aqueles em que têm mais aptidão a partir do próprio CV, e gerarem um rascunho de email pronto para enviar ao coordenador. O nome é um trocadilho: o aluno *aplica* para um projeto, com IA no caminho.

> O repositório hoje contém apenas a **base do catálogo** (scraper FUNAPE + interface estática). As demais funcionalidades estão planejadas e serão construídas em fases — ver [Roadmap](#roadmap).

## Status

| Componente | Estado |
|---|---|
| Scraper FUNAPE (CEIA + INF + AKCIT) | ✅ existe |
| Interface estática de catálogo | ✅ existe |
| Backend FastAPI + Supabase | ⬜ planejado |
| Autenticação por email institucional | ⬜ planejado |
| Match CV ↔ projetos via IA | ⬜ planejado |
| Geração de rascunho de email | ⬜ planejado |
| Scraper de emails do SIGAA | ⬜ planejado |
| Integração Gmail API | ⬜ planejado |
| Tinder de projetos | ⬜ futuro |

## Funcionalidades

### 1. Catálogo (existente)
Interface com cards, busca textual e filtros por **órgão parceiro**, **tipo** e **área**. Cada card mostra descrição do projeto e responsável; o modal exibe metadados completos (vigência, modalidade, instrumento, código de controle).

### 2. Cadastro do aluno
Login via magic link no email institucional (`@ufg.br` / `@discente.ufg.br`). No primeiro acesso o aluno preenche:

- Nome, matrícula, curso e período
- Tipo de vaga buscada: **bolsista**, **voluntário** ou **ambos**
- Áreas de interesse (multi-select com a taxonomia do catálogo)
- Aceite de tratamento de dados (LGPD)

### 3. Match CV ↔ projetos
O aluno faz upload do CV em PDF. O sistema:

1. Extrai o texto do PDF
2. Gera embedding vetorial do CV
3. Busca os 10 projetos mais próximos via **pgvector** (similaridade cosseno)
4. Pede a uma LLM (OpenAI) que ranqueie esses 10 e justifique cada match
5. Apresenta a lista ordenada com a justificativa

### 4. Rascunho de email pro coordenador
Para cada projeto da lista, o aluno pode pedir um rascunho de email. A LLM recebe CV + dados do projeto e gera `assunto + corpo`. No MVP, abre o cliente de email padrão via `mailto:`. Em fase futura, cria o rascunho diretamente na conta Gmail do aluno via API.

Coordenadores podem desativar emails da plataforma a qualquer momento por um link de **opt-out** no rodapé.

### 5. Tinder de projetos *(futuro)*
Apresenta projetos um a um com base nas competências do aluno; like/dislike por swipe. No final do fluxo, mostra os matches e permite enviar emails em lote.

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│ FRONTEND  (Vue 3 + Vite)                                        │
│   - Catálogo  - Login  - Upload CV  - Email preview  - Tinder   │
└────────────────────────────┬────────────────────────────────────┘
                             │ JWT do Supabase Auth
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ BACKEND   (FastAPI no servidor próprio)                         │
│                                                                 │
│   /api/projects          catálogo                               │
│   /api/cv/upload         extrai texto + gera embedding          │
│   /api/match             ranqueia projetos (pgvector + LLM)     │
│   /api/email/draft       gera rascunho                          │
│   /api/opt-out           opt-out de coordenador (público)       │
│   /admin/*               dashboard interno (role admin)         │
│                                                                 │
│   Middleware: validação de JWT, quota mensal por usuário        │
└──┬───────────────┬───────────────────┬──────────────────────────┘
   │               │                   │
   ▼               ▼                   ▼
┌─────────┐  ┌──────────┐  ┌──────────────────────────┐
│Supabase │  │ OpenAI   │  │ Scrapers (manual/cron)   │
│Postgres │  │ API      │  │  - FUNAPE (catálogo)     │
│+pgvector│  │          │  │  - SIGAA (emails docente)│
│+ Auth   │  │          │  │                          │
│+Storage │  │          │  │                          │
└─────────┘  └──────────┘  └──────────────────────────┘
```

## Stack

| Camada | Escolha | Motivo |
|---|---|---|
| Frontend | **Vue 3 + Vite** | Reaproveita o CSS atual, low-ceremony, bom pra Tinder/swipe |
| Backend | **FastAPI** | Async nativo (importante pras chamadas OpenAI), validação Pydantic |
| Banco de dados | **Supabase Postgres** + **pgvector** | DB + Auth + Storage no mesmo lugar; vector search nativo |
| Autenticação | **Supabase Auth** (magic link) | Whitelist de domínio sem código |
| LLM | **OpenAI** (`gpt-4o-mini` + `gpt-4o`) | Custo baixo no matching, qualidade no email |
| Storage de CVs | **Supabase Storage** (bucket privado) | Signed URLs, lifecycle automático |
| Scrapers | **Python stdlib** + **Playwright** (SIGAA) | Sem dependência pesada onde não precisa |
| Hospedagem | Servidor próprio + Caddy (HTTPS) | Definido na fase de deploy |

## Modelo de dados (resumo)

Tabelas principais no Postgres:

- **`profiles`** — extensão de `auth.users` com matrícula, curso, tipo de vaga buscada, áreas de interesse, `role`
- **`projects`** — projetos coletados da FUNAPE com embedding vetorial e email do coordenador (enriquecido pelo SIGAA)
- **`user_cvs`** — CVs enviados (texto extraído + embedding + competências em JSON)
- **`email_drafts`** — rascunhos gerados (assunto, corpo, status de envio)
- **`coordinator_optouts`** — coordenadores que pediram para não receber emails
- **`llm_usage`** — log de cada chamada à LLM (tokens, custo, endpoint) para quota e auditoria
- **`project_swipes`** *(futuro)* — likes/dislikes do Tinder

## Fluxos-chave

### Cadastro
```
Email institucional → magic link → primeiro acesso → preenche perfil → aceita LGPD
```

### Upload CV → Match → Email
```
Upload PDF
  └─ extrai texto (pypdf)
  └─ embedding (text-embedding-3-small)
  └─ salva em user_cvs

Match
  └─ SELECT projects ORDER BY embedding <=> $cv_embedding LIMIT 10
  └─ gpt-4o-mini ranqueia + justifica
  └─ retorna lista pro frontend

Geração de email
  └─ checa quota do usuário e opt-out do coordenador
  └─ gpt-4o gera {subject, body}
  └─ salva em email_drafts
  └─ frontend abre mailto: (MVP) ou cria draft Gmail (v2)
```

### Opt-out do coordenador
```
Email gerado tem footer com link assinado (JWT curto)
  └─ coordenador clica → página pública confirma
  └─ insere em coordinator_optouts
  └─ futuras tentativas de email para esse coordenador são bloqueadas
```

## Privacidade & LGPD

**O que coletamos:** dados básicos do perfil (nome, matrícula, curso), CV em PDF, embeddings derivados, logs de uso.

**Como tratamos:**
- O CV é processado pela OpenAI no momento do upload e do match — informação explícita na tela de consentimento
- CVs ficam armazenados criptografados no Supabase Storage por **90 dias após a última atividade**, depois são apagados automaticamente
- O aluno pode pedir a exclusão completa de seus dados a qualquer momento (endpoint próprio)

**Coordenadores** podem se opor ao recebimento de emails a qualquer momento via link no rodapé de cada email.

## Limites de uso

- Acesso restrito a domínios `@ufg.br` e `@discente.ufg.br`
- **Budget mensal por usuário**: USD 0,50 (≈ 25 matches + 15 emails confortavelmente), reseta dia 1º
- **Budget global mensal**: USD 50,00 — kill switch automático ao atingir
- Anti-spam: máximo **1 email por aluno → mesmo coordenador a cada 30 dias**

## Roadmap

- [ ] **Fase 0** — Pré-requisitos operacionais (Supabase, Google Cloud, domínio)
- [ ] **Fase 1** — Backend FastAPI base + migração `projects.json` → Supabase
- [ ] **Fase 2** — Auth Supabase + cadastro de aluno
- [ ] **Fase 3** — Embeddings + endpoint de match + tela de upload de CV
- [ ] **Fase 4** — Scraper SIGAA para enriquecer emails dos coordenadores
- [ ] **Fase 5** — Geração de email + `mailto:` + opt-out
- [ ] **Fase 6** — Admin dashboard (custo, top users, kill switch)
- [ ] **Fase 7** — Integração Gmail API (rascunho real)
- [ ] **Fase 8** — Formulário de competências (alternativa ao upload de CV)
- [ ] **Fase 9** — Tinder de projetos

## Como rodar (legado — só catálogo estático)

Enquanto a Fase 1 não está pronta, o catálogo continua sendo gerado por scripts Python e servido como site estático.

### Requisitos

- Python 3.10+
- Acesso à internet para consultar a API da FUNAPE

Os scripts usam apenas a biblioteca padrão.

### Coletar projetos ativos

```bash
python scrape_ceia_projetos.py
```

Saída: `ceia_projetos_nao_encerrados.csv`

### Gerar o catálogo classificado

```bash
python build_project_catalog.py
```

Saída: `web/data/projects.json`

### Abrir a interface web

```bash
python -m http.server 4173
```

Acesse: http://127.0.0.1:4173/web/

### Critérios de classificação atuais

**Tipo** — derivado de `lista_modalidade`, `lista_forma_contratacao` e termos do título:
- P&D e Inovação
- Pesquisa Aplicada
- Capacitação e Formação
- Desenvolvimento Científico

**Área** — inferida por regras de palavras-chave em `build_project_catalog.py` (ver constante `AREA_RULES`):
IA Generativa e Conversacional, Educação e Capacitação, Logística e Supply Chain, Saúde, Mobilidade e Veículos, Finanças/Marketing/Negócios, Jurídico, Software e Desenvolvimento, Energia, Gestão e Governança, Visão Computacional, Agro e Alimentos, Construção e BIM, Segurança e Monitoramento.

## Estrutura atual do repositório

```text
.
├── build_project_catalog.py        # CSV → JSON classificado
├── ceia_projetos_nao_encerrados.csv
├── link.txt                         # config do scraper FUNAPE
├── scrape_ceia_projetos.py          # scraper FUNAPE
├── infra
│   └── supabase_schema.sql          # schema completo do banco (Fase 1+)
├── .env.example                     # template de variáveis de ambiente
└── web                              # interface estática
    ├── app.js
    ├── data/projects.json
    ├── index.html
    └── styles.css
```

A partir da Fase 1, novas pastas (`backend/`, `webapp/`, `scrapers/sigaa/`) serão criadas no mesmo repositório. Se ficar bagunçado, o repositório será dividido.
