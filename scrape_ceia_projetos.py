#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


API_BASE_URL = "https://transparencia-api.funape.org.br"
DEFAULT_TIMEOUT = 60
MAX_RETRIES = 3
MAX_WORKERS = 8


@dataclass(frozen=True)
class Config:
    site_url: str
    partner_name: str


def read_config(link_file: Path) -> Config:
    lines = [line.strip() for line in link_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"Arquivo vazio: {link_file}")

    site_url = lines[0]
    partner_name = ""

    for line in lines[1:]:
        lower = line.lower()
        if "org" in lower and "parceiro" in lower and ":" in line:
            partner_name = line.split(":", 1)[1].strip()
            break

    if not partner_name:
        raise ValueError(
            "Não encontrei o filtro de órgão parceiro no link.txt. "
            "Esperado algo como 'orgão parceiro: ...'."
        )

    return Config(site_url=site_url, partner_name=partner_name)


def fetch_json(url: str, timeout: int = DEFAULT_TIMEOUT) -> Any:
    last_error: Exception | None = None
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*",
        },
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt == MAX_RETRIES:
                break
            time.sleep(attempt)

    raise RuntimeError(f"Falha ao buscar {url}: {last_error}") from last_error


def load_project_list() -> list[dict[str, Any]]:
    payload = fetch_json(f"{API_BASE_URL}/projetos/filtro")
    data = payload.get("dados")
    if not isinstance(data, list):
        raise RuntimeError("Resposta inesperada em /projetos/filtro")
    return data


def is_not_closed(status: Any) -> bool:
    return str(status or "").strip().casefold() != "encerrado"


def filter_projects(projects: list[dict[str, Any]], partner_name: str) -> list[dict[str, Any]]:
    filtered = [
        row
        for row in projects
        if row.get("instituicao_executora") == partner_name and is_not_closed(row.get("status"))
    ]
    filtered.sort(key=lambda row: (str(row.get("status") or ""), str(row.get("ccusto") or "")))
    return filtered


def load_project_detail(ccusto: str) -> dict[str, Any]:
    payload = fetch_json(f"{API_BASE_URL}/projetos/{quote(ccusto)}")
    data = payload.get("dados")
    if not isinstance(data, dict):
        raise RuntimeError(f"Resposta inesperada em /projetos/{ccusto}")
    return data


def normalize_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def build_row(
    summary: dict[str, Any],
    detail: dict[str, Any],
    site_url: str,
    partner_name: str,
    fetched_at: str,
) -> dict[str, str]:
    row: dict[str, str] = {
        "site_url": site_url,
        "api_base_url": API_BASE_URL,
        "orgao_parceiro_filtro": partner_name,
        "coletado_em_utc": fetched_at,
    }

    for key, value in summary.items():
        row[f"lista_{key}"] = normalize_value(value)

    for key, value in detail.items():
        row[f"detalhe_{key}"] = normalize_value(value)

    return row


def write_csv(rows: list[dict[str, str]], output_file: Path) -> None:
    all_columns: list[str] = []
    seen_columns: set[str] = set()

    for row in rows:
        for key in row:
            if key not in seen_columns:
                seen_columns.add(key)
                all_columns.append(key)

    with output_file.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=all_columns)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    workdir = Path(__file__).resolve().parent
    link_file = workdir / "link.txt"
    output_file = workdir / "ceia_projetos_nao_encerrados.csv"

    config = read_config(link_file)
    projects = load_project_list()
    filtered_projects = filter_projects(projects, config.partner_name)

    fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    details_by_ccusto: dict[str, dict[str, Any]] = {}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {
            executor.submit(load_project_detail, str(project["ccusto"])): str(project["ccusto"])
            for project in filtered_projects
        }
        for future in as_completed(future_map):
            ccusto = future_map[future]
            details_by_ccusto[ccusto] = future.result()

    rows = [
        build_row(
            summary=project,
            detail=details_by_ccusto[str(project["ccusto"])],
            site_url=config.site_url,
            partner_name=config.partner_name,
            fetched_at=fetched_at,
        )
        for project in filtered_projects
    ]

    write_csv(rows, output_file)

    print(f"Projetos encontrados: {len(filtered_projects)}")
    print(f"CSV gerado em: {output_file}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        raise SystemExit(1)
