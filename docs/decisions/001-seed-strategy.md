# ADR 001 — Estratégia de seed da tabela `projects`

**Status:** aceita
**Data:** 2026-04-24
**Fase:** 1

## Contexto

A Fase 1 precisa popular a tabela `public.projects` no Supabase com os dados que hoje vivem em `web/data/projects.json` (gerado pelo scraper FUNAPE). O scraper roda periodicamente e produz JSON; alguém precisa empurrar esse JSON pro banco.

Três formas óbvias de fazer isso:

1. **Script CLI one-shot** (`backend/scripts/seed_projects.py`), rodado manualmente ou via cron.
2. **Endpoint admin** (`POST /admin/projects/sync`) protegido por role `admin` do Supabase Auth.
3. **Trigger direto no scraper** — o próprio `build_project_catalog.py` já faria o upsert em vez de só gerar JSON.

## Decisão

Adotamos a opção 1 — script CLI one-shot.

## Motivo

- **Endpoint admin exige Auth**, que é Fase 2. Adotar endpoint agora força ordem de implementação errada (auth antes de ter o que autenticar).
- **Trigger no scraper** acopla duas responsabilidades num script só (coleta + persistência). Pior, obriga o scraper a ter credencial de banco, o que espalha o `SUPABASE_SERVICE_ROLE_KEY` por mais processos.
- **Script CLI casa com o padrão existente**: o scraper já é CLI standalone, idempotente e pensado pra rodar periodicamente. Adicionar mais um script segue o mesmo formato operacional.
- **Fácil de virar cron** quando o SIGAA scraper (Fase 4) precisar refresh semanal dos projetos. Sem mudança de forma — mesma CLI rodada em schedule.
- **Baixo custo de migrar pra endpoint depois.** Se na Fase 6 (admin dashboard) fizer sentido ter um botão "sincronizar catálogo", basta embrulhar o `main()` do script num handler FastAPI.

## Como reverter

Se virar admin endpoint no futuro:

1. Extrair o corpo de `seed_projects.main()` para uma função pura (`sync_projects_from_json()` em `backend/app/services/projects.py`).
2. Criar handler `POST /admin/projects/sync` que chama essa função.
3. Proteger com dependência que valida `role == 'admin'` no JWT do Supabase.
4. Manter o script CLI chamando a mesma função — as duas formas coexistem sem duplicação.

## Consequências

- Por enquanto, manter o catálogo em dia depende de alguém rodar `python backend/scripts/seed_projects.py` após cada execução do scraper.
- Até existir a Fase 2, não há forma autenticada via web de acionar seed. Aceitável: o operador do scraper é o mesmo dev rodando o projeto.
- Se o scraper passar a ter múltiplos consumidores (ex.: SIGAA enriquecendo emails), considerar mover a lógica para um serviço em `backend/app/services/` reutilizável pelo CLI e por um futuro endpoint.
