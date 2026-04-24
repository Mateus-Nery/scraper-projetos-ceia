"""Upsert projects from web/data/projects.json into Supabase.

Run: `python backend/scripts/seed_projects.py`

Reads the catalog JSON produced by scraper/build_project_catalog.py and
upserts each project into public.projects. Idempotent — re-running is
safe and only overwrites mutable fields.

See docs/decisions/001-seed-strategy.md for why this is a CLI script
rather than an admin endpoint.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Allow running this file directly: `python backend/scripts/seed_projects.py`
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.db import get_supabase  # noqa: E402


CATALOG_JSON = REPO_ROOT / "web" / "data" / "projects.json"

PARTNER_GROUP_MAP = {
    "CEIA": "CEIA",
    "AKCIT": "AKCIT",
    "Instituto de Informática": "INF",
}


def map_partner_group(raw: str) -> str:
    return PARTNER_GROUP_MAP.get(raw, "OUTRO")


def parse_br_date(value: str) -> str | None:
    """FUNAPE entrega datas em DD/MM/YYYY; Postgres quer ISO."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%d/%m/%Y").date().isoformat()
    except ValueError:
        return None


def to_db_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "title": item["rawTitle"] or item["description"],
        "description": item["description"],
        "responsible_name": item["responsible"],
        "partner_group": map_partner_group(item["partnerGroup"]),
        "partner_name": item["partnerName"] or item["partner"],
        "area": item["area"],
        "project_type": item["type"],
        "modality": item["modality"],
        "agreement_type": item["agreementType"],
        "status": item["status"],
        "contractor": item["contractor"],
        "start_date": parse_br_date(item["startDate"]),
        "end_date": parse_br_date(item["endDate"]),
        "value_text": item["value"],
        "control_code": item["controlCode"],
        "raw_data": item,
    }


def main() -> int:
    if not CATALOG_JSON.exists():
        print(f"Catálogo não encontrado: {CATALOG_JSON}", file=sys.stderr)
        print("Rode antes: python scraper/build_project_catalog.py", file=sys.stderr)
        return 1

    payload = json.loads(CATALOG_JSON.read_text(encoding="utf-8"))
    items = payload.get("projects", [])
    if not items:
        print("Nenhum projeto no JSON — nada a fazer.")
        return 0

    rows = [to_db_row(item) for item in items if item.get("id")]

    client = get_supabase()
    response = client.table("projects").upsert(rows, on_conflict="id").execute()

    inserted = len(response.data or [])
    print(f"Projetos lidos do JSON: {len(items)}")
    print(f"Linhas upserted no Supabase: {inserted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
