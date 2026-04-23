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
class FilterRule:
    partner_name: str
    statuses: tuple[str, ...]
    modalities: tuple[str, ...]


@dataclass(frozen=True)
class Config:
    site_url: str
    rules: tuple[FilterRule, ...]


def normalize_text(value: str) -> str:
    return value.strip().casefold()


def read_config(link_file: Path) -> Config:
    raw_lines = link_file.read_text(encoding="utf-8").splitlines()
    non_empty_lines = [line.strip() for line in raw_lines if line.strip()]
    if not non_empty_lines:
        raise ValueError(f"Arquivo vazio: {link_file}")

    site_url = non_empty_lines[0]
    rules_data: list[dict[str, list[str] | str]] = []
    current_rule: dict[str, list[str] | str] | None = None

    def push_current_rule() -> None:
        if not current_rule:
            return
        partner_name = str(current_rule.get("partner_name", "")).strip()
        if not partner_name:
            return
        statuses = tuple(
            value.strip()
            for value in current_rule.get("statuses", [])  # type: ignore[arg-type]
            if str(value).strip()
        ) or ("Ativo",)
        modalities = tuple(
            value.strip()
            for value in current_rule.get("modalities", [])  # type: ignore[arg-type]
            if str(value).strip()
        )
        rules_data.append(
            {
                "partner_name": partner_name,
                "statuses": list(statuses),
                "modalities": list(modalities),
            }
        )

    for raw_line in raw_lines[raw_lines.index(non_empty_lines[0]) + 1 :]:
        line = raw_line.strip()
        if not line:
            continue
        if line == "---":
            push_current_rule()
            current_rule = None
            continue
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        key_normalized = normalize_text(key)
        value = value.strip()
        current_rule = current_rule or {"partner_name": "", "statuses": [], "modalities": []}

        if "org" in key_normalized and "parceiro" in key_normalized:
            if str(current_rule.get("partner_name", "")).strip():
                push_current_rule()
                current_rule = {"partner_name": "", "statuses": [], "modalities": []}
            current_rule["partner_name"] = value
        elif "modalidade" in key_normalized:
            current_rule["modalities"] = [*current_rule["modalities"], value]  # type: ignore[index]
        elif "status" in key_normalized:
            current_rule["statuses"] = [*current_rule["statuses"], value]  # type: ignore[index]

    push_current_rule()

    if not rules_data:
        raise ValueError(
            "Não encontrei regras válidas no link.txt. "
            "Use pelo menos uma linha 'orgão parceiro: ...'."
        )

    rules = tuple(
        FilterRule(
            partner_name=str(rule["partner_name"]),
            statuses=tuple(rule["statuses"]),  # type: ignore[arg-type]
            modalities=tuple(rule["modalities"]),  # type: ignore[arg-type]
        )
        for rule in rules_data
    )
    return Config(site_url=site_url, rules=rules)


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


def matches_rule(project: dict[str, Any], rule: FilterRule) -> bool:
    partner_name = str(project.get("instituicao_executora") or "").strip()
    status = str(project.get("status") or "").strip()
    modality = str(project.get("modalidade") or "").strip()

    if partner_name != rule.partner_name:
        return False
    if rule.statuses and normalize_text(status) not in {normalize_text(item) for item in rule.statuses}:
        return False
    if rule.modalities and normalize_text(modality) not in {normalize_text(item) for item in rule.modalities}:
        return False
    return True


def filter_projects(
    projects: list[dict[str, Any]], rules: tuple[FilterRule, ...]
) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    filtered_by_ccusto: dict[str, dict[str, Any]] = {}
    matched_rules_by_ccusto: dict[str, list[str]] = {}

    for rule in rules:
        rule_label = rule.partner_name
        if rule.modalities:
            rule_label = f"{rule.partner_name} | modalidades: {', '.join(rule.modalities)}"

        for row in projects:
            if not matches_rule(row, rule):
                continue
            ccusto = str(row.get("ccusto") or "").strip()
            if not ccusto:
                continue
            filtered_by_ccusto[ccusto] = row
            matched_rules_by_ccusto.setdefault(ccusto, []).append(rule_label)

    filtered = sorted(
        filtered_by_ccusto.values(),
        key=lambda row: (
            str(row.get("instituicao_executora") or ""),
            str(row.get("modalidade") or ""),
            str(row.get("ccusto") or ""),
        ),
    )
    return filtered, matched_rules_by_ccusto


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
    matched_rules: list[str],
    fetched_at: str,
) -> dict[str, str]:
    row: dict[str, str] = {
        "site_url": site_url,
        "api_base_url": API_BASE_URL,
        "orgao_parceiro_filtro": normalize_value(summary.get("instituicao_executora")),
        "regras_coleta": " | ".join(matched_rules),
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
    filtered_projects, matched_rules_by_ccusto = filter_projects(projects, config.rules)

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
            matched_rules=matched_rules_by_ccusto.get(str(project["ccusto"]), []),
            fetched_at=fetched_at,
        )
        for project in filtered_projects
    ]

    write_csv(rows, output_file)

    print("Regras aplicadas:")
    for rule in config.rules:
        modalities = ", ".join(rule.modalities) if rule.modalities else "todas"
        statuses = ", ".join(rule.statuses) if rule.statuses else "qualquer"
        print(f"- {rule.partner_name} | status: {statuses} | modalidades: {modalities}")
    print(f"Projetos encontrados: {len(filtered_projects)}")
    print(f"CSV gerado em: {output_file}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        raise SystemExit(1)
