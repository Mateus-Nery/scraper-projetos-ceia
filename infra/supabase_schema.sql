-- =====================================================================
-- AplicAI — schema Supabase / Postgres
-- =====================================================================
-- Como aplicar:
--   1. Crie o projeto no Supabase (region: South America - São Paulo)
--   2. Vá em SQL Editor
--   3. Cole este arquivo inteiro e clique em "Run"
--   4. Tabelas e policies serão criadas; estruturas idempotentes (re-rodar é seguro)
--
-- Convenções:
--   - Todas as tabelas têm RLS habilitado (Supabase exige)
--   - Backend FastAPI usa SERVICE_ROLE_KEY → bypassa RLS naturalmente
--   - Frontend Vue usa ANON_KEY → respeita as policies definidas aqui
-- =====================================================================


-- =====================================================================
-- EXTENSIONS
-- =====================================================================
-- uuid-ossp já vem instalada no schema `extensions` no Supabase.
-- Instalamos pgvector no mesmo schema (best practice: evitar extensões em `public`).
CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA extensions;
CREATE EXTENSION IF NOT EXISTS vector       WITH SCHEMA extensions;


-- =====================================================================
-- ENUMS
-- =====================================================================
DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('student', 'admin');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE vacancy_type AS ENUM ('bolsista', 'voluntario', 'ambos');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE partner_group AS ENUM ('CEIA', 'INF', 'AKCIT', 'OUTRO');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- =====================================================================
-- FASE 2: profiles (extensão de auth.users)
-- =====================================================================
CREATE TABLE IF NOT EXISTS profiles (
    id              uuid PRIMARY KEY REFERENCES auth.users ON DELETE CASCADE,
    email           text NOT NULL,
    full_name       text,
    matricula       text,
    curso           text,
    periodo         smallint,
    vacancy_type    vacancy_type,
    interest_areas  text[] DEFAULT '{}',
    role            user_role NOT NULL DEFAULT 'student',
    lgpd_accepted_at timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

-- Cria profile automaticamente quando user faz signup via Supabase Auth.
-- `SET search_path` é obrigatório em SECURITY DEFINER pra evitar hijack via schema injection.
CREATE OR REPLACE FUNCTION handle_new_user() RETURNS trigger
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path = public, pg_temp
AS $$
BEGIN
    INSERT INTO public.profiles (id, email)
    VALUES (NEW.id, NEW.email)
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();


-- =====================================================================
-- FASE 1: projects (catálogo da FUNAPE + email enriquecido pelo SIGAA)
-- =====================================================================
CREATE TABLE IF NOT EXISTS projects (
    id                          text PRIMARY KEY,             -- ccusto da FUNAPE
    title                       text NOT NULL,
    description                 text,
    responsible_name            text,
    responsible_email           text,                          -- preenchido pelo scraper SIGAA (Fase 4)
    responsible_opted_out       boolean NOT NULL DEFAULT false,
    partner_group               partner_group NOT NULL DEFAULT 'OUTRO',
    partner_name                text,
    area                        text,
    project_type                text,
    modality                    text,
    agreement_type              text,
    status                      text,
    contractor                  text,
    start_date                  date,
    end_date                    date,
    value_text                  text,                          -- formato vem como string da FUNAPE
    control_code                text,
    raw_data                    jsonb,                         -- payload completo, pra rastreabilidade
    embedding                   vector(1536),                  -- text-embedding-3-small = 1536 dims
    created_at                  timestamptz NOT NULL DEFAULT now(),
    updated_at                  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS projects_partner_group_idx ON projects(partner_group);
CREATE INDEX IF NOT EXISTS projects_area_idx ON projects(area);
-- Index de similaridade vetorial (será populado quando tivermos dados)
-- CREATE INDEX projects_embedding_idx ON projects USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);


-- =====================================================================
-- FASE 3: user_cvs
-- =====================================================================
CREATE TABLE IF NOT EXISTS user_cvs (
    id                  uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id             uuid NOT NULL REFERENCES auth.users ON DELETE CASCADE,
    storage_path        text NOT NULL,                  -- caminho no Supabase Storage
    raw_text            text,                            -- texto extraído do PDF
    competencies        jsonb,                           -- estrutura extraída pela LLM
    embedding           vector(1536),
    last_used_at        timestamptz NOT NULL DEFAULT now(),
    uploaded_at         timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS user_cvs_user_id_idx ON user_cvs(user_id);
CREATE INDEX IF NOT EXISTS user_cvs_last_used_idx ON user_cvs(last_used_at);


-- =====================================================================
-- FASE 5: email_drafts
-- =====================================================================
CREATE TABLE IF NOT EXISTS email_drafts (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         uuid NOT NULL REFERENCES auth.users ON DELETE CASCADE,
    project_id      text NOT NULL REFERENCES projects ON DELETE CASCADE,
    subject         text NOT NULL,
    body            text NOT NULL,
    sent            boolean NOT NULL DEFAULT false,
    sent_at         timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS email_drafts_user_idx ON email_drafts(user_id);
CREATE INDEX IF NOT EXISTS email_drafts_project_idx ON email_drafts(project_id);
-- Anti-spam: 1 email/aluno → mesmo coordenador a cada N dias (validar no backend usando esse índice)
CREATE INDEX IF NOT EXISTS email_drafts_user_project_created_idx
    ON email_drafts(user_id, project_id, created_at);


-- =====================================================================
-- FASE 5: coordinator_optouts
-- =====================================================================
CREATE TABLE IF NOT EXISTS coordinator_optouts (
    email           text PRIMARY KEY,
    opted_out_at    timestamptz NOT NULL DEFAULT now(),
    reason          text
);


-- =====================================================================
-- FASE 3+: llm_usage (cost tracking + rate limit)
-- =====================================================================
CREATE TABLE IF NOT EXISTS llm_usage (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         uuid REFERENCES auth.users ON DELETE SET NULL,
    endpoint        text NOT NULL,              -- 'match' | 'email_draft' | 'cv_extract' | 'embedding'
    model           text NOT NULL,
    tokens_in       int NOT NULL DEFAULT 0,
    tokens_out      int NOT NULL DEFAULT 0,
    cost_usd        numeric(10,6) NOT NULL DEFAULT 0,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS llm_usage_user_created_idx ON llm_usage(user_id, created_at);
CREATE INDEX IF NOT EXISTS llm_usage_created_idx ON llm_usage(created_at);


-- =====================================================================
-- FASE 9 (futuro): project_swipes — Tinder
-- =====================================================================
CREATE TABLE IF NOT EXISTS project_swipes (
    user_id         uuid NOT NULL REFERENCES auth.users ON DELETE CASCADE,
    project_id      text NOT NULL REFERENCES projects ON DELETE CASCADE,
    liked           boolean NOT NULL,
    swiped_at       timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, project_id)
);


-- =====================================================================
-- ROW LEVEL SECURITY
-- =====================================================================
ALTER TABLE profiles                ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects                ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_cvs                ENABLE ROW LEVEL SECURITY;
ALTER TABLE email_drafts            ENABLE ROW LEVEL SECURITY;
ALTER TABLE coordinator_optouts     ENABLE ROW LEVEL SECURITY;
ALTER TABLE llm_usage               ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_swipes          ENABLE ROW LEVEL SECURITY;

-- profiles: usuário lê/edita o próprio
DROP POLICY IF EXISTS "profiles_self_read" ON profiles;
CREATE POLICY "profiles_self_read" ON profiles
    FOR SELECT USING (auth.uid() = id);

DROP POLICY IF EXISTS "profiles_self_update" ON profiles;
CREATE POLICY "profiles_self_update" ON profiles
    FOR UPDATE USING (auth.uid() = id);

-- projects: qualquer autenticado lê
DROP POLICY IF EXISTS "projects_authenticated_read" ON projects;
CREATE POLICY "projects_authenticated_read" ON projects
    FOR SELECT USING (auth.role() = 'authenticated');

-- user_cvs: usuário só vê os próprios
DROP POLICY IF EXISTS "user_cvs_self_all" ON user_cvs;
CREATE POLICY "user_cvs_self_all" ON user_cvs
    FOR ALL USING (auth.uid() = user_id);

-- email_drafts: usuário só vê os próprios
DROP POLICY IF EXISTS "email_drafts_self_all" ON email_drafts;
CREATE POLICY "email_drafts_self_all" ON email_drafts
    FOR ALL USING (auth.uid() = user_id);

-- llm_usage: usuário só vê o próprio uso
DROP POLICY IF EXISTS "llm_usage_self_read" ON llm_usage;
CREATE POLICY "llm_usage_self_read" ON llm_usage
    FOR SELECT USING (auth.uid() = user_id);

-- project_swipes: usuário só vê os próprios swipes
DROP POLICY IF EXISTS "project_swipes_self_all" ON project_swipes;
CREATE POLICY "project_swipes_self_all" ON project_swipes
    FOR ALL USING (auth.uid() = user_id);

-- coordinator_optouts: nenhuma policy intencionalmente → só backend (service_role) lê/escreve.
-- O advisor "rls_enabled_no_policy" é INFO e pode ser ignorado nesta tabela específica.


-- =====================================================================
-- STORAGE BUCKET (criar manualmente no painel do Supabase)
-- =====================================================================
-- Bucket name: cvs
-- Public:      false
-- File size limit: 5 MB
-- Allowed MIME types: application/pdf
-- Policies do bucket: backend usa service_role (bypassa); frontend não acessa direto
