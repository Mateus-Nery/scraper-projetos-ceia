# AplicAI — Backend

FastAPI que serve o catálogo (Fase 1) e vai crescer até cobrir match CV/IA, geração de email e admin (Fases 3–7).

## Requisitos

- Python 3.10+ (`.python-version` fixa 3.10.11)
- Um `.env` na raiz do repo (copie de `.env.example` e preencha `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`)
- Schema do Supabase já aplicado — ver `infra/supabase_schema.sql`

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
```

## Rodar o servidor

```bash
uvicorn backend.app.main:app --reload --port 8000
```

Endpoints disponíveis nesta fase:

- `GET /health` — smoke test
- `GET /api/projects` — lista projetos (filtros opcionais: `partner_group`, `area`, `project_type`, `limit`)

## Popular o Supabase a partir do JSON estático

```bash
python backend/scripts/seed_projects.py
```

Lê `web/data/projects.json` (gerado pelo scraper) e faz upsert em `public.projects`. Idempotente — pode rodar quantas vezes quiser. Ver `docs/decisions/001-seed-strategy.md` para a justificativa dessa abordagem.

## Estrutura

```
backend/
├── app/
│   ├── main.py              # FastAPI app + CORS + routers
│   ├── config.py            # pydantic-settings lê o .env da raiz
│   ├── db.py                # cliente Supabase (service_role, bypassa RLS)
│   └── routers/
│       └── projects.py      # GET /api/projects
├── scripts/
│   └── seed_projects.py     # projects.json → Supabase upsert
└── requirements.txt
```
