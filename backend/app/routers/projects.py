from typing import Any

from fastapi import APIRouter, Query

from ..db import get_supabase


router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("")
def list_projects(
    partner_group: str | None = Query(default=None, description="CEIA | INF | AKCIT | OUTRO"),
    area: str | None = Query(default=None),
    project_type: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=1000),
) -> dict[str, Any]:
    query = get_supabase().table("projects").select(
        "id,title,description,responsible_name,partner_group,partner_name,"
        "area,project_type,modality,status,start_date,end_date,value_text"
    )
    if partner_group:
        query = query.eq("partner_group", partner_group)
    if area:
        query = query.eq("area", area)
    if project_type:
        query = query.eq("project_type", project_type)

    response = query.order("title").limit(limit).execute()
    projects = response.data or []
    return {"count": len(projects), "projects": projects}
