#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
SOURCE_CSV = ROOT / "ceia_projetos_nao_encerrados.csv"
OUTPUT_JSON = ROOT / "web" / "data" / "projects.json"


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return ascii_only.lower()


def clean_whitespace(value: str) -> str:
    value = value.replace("_", " - ")
    value = re.sub(r"(?<=\w)-(?=\w)", " - ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" -")


def title_case_name(value: str) -> str:
    clean = clean_whitespace(value).title()
    replacements = {
        "Ia": "IA",
        "Ceia": "CEIA",
        "Embrapii": "EMBRAPII",
        "Sebrae": "SEBRAE",
        "Gpt": "GPT",
        "Rlhf": "RLHF",
        "Bim": "BIM",
        "Flv": "FLV",
        "Samd": "SAMD",
        "Open-Rmf": "Open-RMF",
        "P&D": "P&D",
        "Llms": "LLMs",
        "Llm": "LLM",
    }
    for source, target in replacements.items():
        clean = re.sub(rf"\b{re.escape(source)}\b", target, clean)
    return clean


def strip_funding_suffix(title: str) -> str:
    clean = clean_whitespace(title)
    parts = re.split(r"\s+-\s+", clean)
    if len(parts) == 1:
        return clean

    funding_tokens = {
        "embrapii",
        "sebrae",
        "empresa",
        "filha",
        "pequena",
        "emprappi",
        "emprapii",
        "sebre",
        "sebraei",
    }

    while len(parts) > 1:
        tail_tokens = re.findall(r"[a-z0-9]+", normalize_text(parts[-1]))
        if tail_tokens and all(token in funding_tokens for token in tail_tokens):
            parts.pop()
            continue
        break

    return " - ".join(parts).strip(" -")


def classify_type(title: str, modality: str, agreement_type: str) -> str:
    normalized_title = normalize_text(title)
    normalized_modality = normalize_text(modality)
    normalized_agreement = normalize_text(agreement_type)

    if any(token in normalized_title for token in ("capacitacao", "treino", "treinos", "habilidades")):
        return "Capacitação e Formação"

    if "desenvolvimento cientifico" in normalized_modality:
        return "Desenvolvimento Científico"
    if "p&d e inovacao" in normalized_modality:
        return "P&D e Inovação"
    if "pesquisa" in normalized_modality:
        return "Pesquisa Aplicada"
    if "acordo" in normalized_agreement:
        return "Acordo e Cooperação"
    if agreement_type:
        return agreement_type.strip().title()
    return "Não classificado"


def classify_partner_group(partner_name: str) -> str:
    normalized_partner = normalize_text(partner_name)
    if "polo embrapii ceia" in normalized_partner:
        return "CEIA"
    if "akcit" in normalized_partner or "tecnologias imersivas" in normalized_partner:
        return "AKCIT"
    if "instituto de informatica" in normalized_partner:
        return "Instituto de Informática"
    return title_case_name(partner_name) if partner_name else "Órgão não informado"


AREA_RULES: list[tuple[str, tuple[str, ...]]] = [
    (
        "Saúde",
        (
            "saude",
            "medical",
            "medic",
            "paciente",
            "prontuario",
            "odont",
            "dental",
            "raio x",
            "raio-x",
            "parentalidade",
            "sonhos lucidos",
            "bem estar",
            "bem-estar",
        ),
    ),
    (
        "Energia",
        (
            "energia",
            "eletrico",
            "combust",
            "fornos",
            "combustao",
            "distribuicao de combustiveis",
        ),
    ),
    (
        "Jurídico",
        (
            "juridic",
            "documentos juridicos",
            "processos juridicos",
            "advocatic",
        ),
    ),
    (
        "Logística e Supply Chain",
        (
            "estoque",
            "estoques",
            "fretes",
            "logistica",
            "smart stores",
            "demanda",
            "vendas",
            "cadeia de suprimentos",
            "centros de distribuicao",
            "compras publicas",
        ),
    ),
    (
        "Mobilidade e Veículos",
        (
            "veicul",
            "automot",
            "frotas",
            "cidades inteligentes",
            "oficinas mecanicas",
            "transporte",
            "urbano brasileiro",
            "embarcacoes",
            "nao tripuladas",
            "navegacao autonoma",
        ),
    ),
    (
        "Educação e Capacitação",
        (
            "capacitacao",
            "educacao",
            "habilidades",
            "corporativo",
            "treino",
            "treinos",
            "esforco",
            "aprendizado personalizado",
            "competencias",
            "conhecimento",
        ),
    ),
    (
        "Agro e Alimentos",
        (
            "bovinos",
            "flv",
            "agro",
            "pecuar",
            "alimento",
        ),
    ),
    (
        "Construção e BIM",
        (
            "construcao",
            "bim",
        ),
    ),
    (
        "Finanças, Marketing e Negócios",
        (
            "financeira",
            "marketing",
            "negocios",
            "clientes",
            "matches",
            "prospeccao",
            "feedbacks de usuarios",
        ),
    ),
    (
        "Robótica, IoT e Redes",
        (
            "robo",
            "robos",
            "open-rmf",
            "conectividade",
            "internet",
            "recursos de rede",
            "provedores modernos de servicos de internet",
        ),
    ),
    (
        "Segurança e Monitoramento",
        (
            "seguranca",
            "safeai",
            "monitoramento",
        ),
    ),
    (
        "Indústria e Operações",
        (
            "industriais",
            "produto automotivo",
            "otimizacao operacional",
            "fornos de combustao",
            "operacional",
        ),
    ),
    (
        "Software e Desenvolvimento",
        (
            "software",
            "casos de teste",
            "ciclo de vida do software",
            "desenvolvimento de software",
            "ai2soft",
            "llms",
        ),
    ),
    (
        "Gestão e Governança",
        (
            "gestao de projetos",
            "tomada de decisao",
            "coordenacao de projetos",
            "framework preditivo",
            "consultor empresarial",
        ),
    ),
    (
        "Visão Computacional",
        (
            "visao computacional",
            "video",
            "videos",
            "imagem",
            "imagens",
            "biometr",
            "anomalias",
            "similaridade",
            "reconhecimento de bovinos",
            "contagem de itens",
        ),
    ),
    (
        "IA Generativa e Conversacional",
        (
            "gpt",
            "linguagem natural",
            "large language models",
            "agentes conversacionais",
            "assistente",
            "bots",
            "sintetizacao de voz",
            "voz",
            "multimodal",
            "agentes inteligentes",
            "conversacional",
            "conteudo multimidia",
            "modelos massivos de linguagem",
            "documentos",
            "aidbot",
        ),
    ),
]


def classify_area(title: str) -> str:
    normalized_title = normalize_text(clean_whitespace(title))
    for area, keywords in AREA_RULES:
        if any(keyword in normalized_title for keyword in keywords):
            return area
    return "Outras"


def build_project(row: dict[str, str]) -> dict[str, Any]:
    raw_title = row.get("lista_projeto", "").strip()
    cleaned_title = strip_funding_suffix(raw_title)
    description = title_case_name(cleaned_title or raw_title)
    responsible = title_case_name(row.get("lista_coordenador") or "").strip() or "Responsável não informado"
    project_type = classify_type(
        title=raw_title,
        modality=row.get("lista_modalidade", ""),
        agreement_type=row.get("lista_forma_contratacao", ""),
    )
    area = classify_area(raw_title)
    partner_name = row.get("lista_instituicao_executora", "").strip()
    partner_group = classify_partner_group(partner_name)

    return {
        "id": row.get("lista_ccusto", "").strip(),
        "description": description,
        "responsible": responsible,
        "type": project_type,
        "area": area,
        "partnerGroup": partner_group,
        "partnerName": partner_name,
        "rawTitle": raw_title,
        "modality": row.get("lista_modalidade", "").strip(),
        "agreementType": row.get("lista_forma_contratacao", "").strip(),
        "status": row.get("lista_status", "").strip(),
        "partner": partner_name,
        "contractor": row.get("lista_instituicao_contratante", "").strip(),
        "startDate": row.get("lista_data_inicio", "").strip(),
        "endDate": row.get("lista_data_fim", "").strip(),
        "value": row.get("lista_valor", "").strip(),
        "controlCode": row.get("detalhe_cod_controle_externo", "").strip(),
    }


def count_by(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    counter = Counter(item[key] for item in items)
    return [
        {"label": label, "count": count}
        for label, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]


def main() -> None:
    with SOURCE_CSV.open("r", encoding="utf-8-sig", newline="") as csv_file:
        rows = list(csv.DictReader(csv_file))

    projects = [build_project(row) for row in rows]
    projects.sort(key=lambda item: item["description"])

    payload = {
        "generatedFrom": SOURCE_CSV.name,
        "projectCount": len(projects),
        "partnerCounts": count_by(projects, "partnerGroup"),
        "areaCounts": count_by(projects, "area"),
        "typeCounts": count_by(projects, "type"),
        "projects": projects,
    }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Projetos processados: {len(projects)}")
    print(f"Áreas: {len(payload['areaCounts'])}")
    print(f"Tipos: {len(payload['typeCounts'])}")
    print(f"Arquivo gerado: {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
