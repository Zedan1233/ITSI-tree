"""Export the ITSI service tree, KPIs, and glass tables without event data."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from . import client

ROOT = Path(__file__).resolve().parent.parent
EXPORT_DIR = ROOT / "export"
HOST_RE = re.compile(r"https://[A-Za-z0-9.-]+\.splunk\.show(?::\d+)?")
TOKEN_RE = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")

KPI_FIELDS = (
    "title",
    "type",
    "search_type",
    "base_search",
    "threshold_field",
    "aggregate_statop",
    "entity_statop",
    "unit",
    "urgency",
    "alert_period",
    "search_alert_earliest",
    "enabled",
    "aggregate_thresholds",
    "entity_thresholds",
)


def include_glass_table(title: str) -> bool:
    return title.startswith("QNB")


def slug(title: str) -> str:
    parts = []
    for char in title.lower():
        parts.append(char if char.isalnum() else "-")
    text = "".join(parts).strip("-")
    while "--" in text:
        text = text.replace("--", "-")
    return text or "untitled"


def id_labels(services: list[dict]) -> dict[str, str]:
    labels = {}
    for service in services:
        key = service.get("_key")
        title = service.get("title") or ""
        if key and title:
            labels[str(key)] = title
        for kpi in service.get("kpis") or []:
            kpi_key = kpi.get("_key")
            kpi_title = kpi.get("title") or "KPI"
            if kpi_key and title:
                labels[str(kpi_key)] = f"{title} / {kpi_title}"
    return labels


def rewrite(value, labels: dict[str, str]):
    """Drop instance hosts and replace ITSI ids with readable titles."""
    if isinstance(value, str):
        value = HOST_RE.sub("", value)
        value = TOKEN_RE.sub("", value)
        for key in sorted(labels, key=len, reverse=True):
            if key and key in value:
                value = value.replace(key, "{{" + labels[key] + "}}")
        return value
    if isinstance(value, list):
        return [rewrite(item, labels) for item in value]
    if isinstance(value, dict):
        return {key: rewrite(item, labels) for key, item in value.items()}
    return value


def portable_kpi(kpi: dict) -> dict | None:
    title = (kpi.get("title") or "").lower()
    if kpi.get("type") == "service_health" or "health score" in title or str(kpi.get("_key", "")).startswith("SHKPI"):
        return None
    kept = {field: kpi.get(field) for field in KPI_FIELDS if field in kpi}
    return kept or None


def portable_service(service: dict, labels: dict[str, str]) -> dict:
    depends = []
    for dep in service.get("services_depends_on") or []:
        child_id = str(dep.get("serviceid") or "")
        depends.append(labels.get(child_id, child_id))
    kpis = []
    for kpi in service.get("kpis") or []:
        portable = portable_kpi(kpi)
        if portable:
            kpis.append(portable)
    return {
        "title": service.get("title"),
        "description": service.get("description") or "",
        "enabled": service.get("enabled", 1),
        "depends_on": depends,
        "kpis": rewrite(kpis, labels),
    }


def portable_glass(table: dict, labels: dict[str, str]) -> dict:
    return {
        "title": table.get("title"),
        "description": table.get("description") or "",
        "definition": rewrite(table.get("definition") or {}, labels),
    }


def _services() -> list[dict]:
    _, listed = client.request(
        "GET",
        "/servicesNS/nobody/SA-ITOA/itoa_interface/service",
        query={"fields": "title,_key", "limit": "500"},
    )
    services = []
    for item in listed or []:
        if isinstance(item, dict) and item.get("_key"):
            services.append(client.get_service(item["_key"]))
    return services


def _glass_tables() -> list[dict]:
    _, listed = client.request(
        "GET",
        "/servicesNS/nobody/SA-ITOA/itoa_interface/glass_table",
        query={"fields": "title,_key", "limit": "100"},
    )
    tables = []
    for item in listed or []:
        if not isinstance(item, dict) or not item.get("_key"):
            continue
        title = item.get("title") or ""
        if not include_glass_table(title):
            print(f"skip glass table outside the QNB environment: {title}")
            continue
        _, table = client.request(
            "GET",
            f"/servicesNS/nobody/SA-ITOA/itoa_interface/glass_table/{item['_key']}",
        )
        if isinstance(table, dict):
            tables.append(table)
    return tables


def write_export(services: list[dict], tables: list[dict], out_dir: Path = EXPORT_DIR) -> dict:
    labels = id_labels(services)
    portable_services = [portable_service(service, labels) for service in services]
    portable_services.sort(key=lambda item: item["title"] or "")
    glass = [portable_glass(table, labels) for table in tables]
    glass.sort(key=lambda item: item["title"] or "")

    if out_dir.exists():
        for path in out_dir.glob("glass-tables/*.json"):
            path.unlink()
    (out_dir / "glass-tables").mkdir(parents=True, exist_ok=True)
    (out_dir / "services.json").write_text(json.dumps(portable_services, indent=2) + "\n")
    written = []
    for table in glass:
        name = slug(table["title"] or "glass-table") + ".json"
        (out_dir / "glass-tables" / name).write_text(json.dumps(table, indent=2) + "\n")
        written.append(name)
    manifest = {
        "exported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "includes": ["services", "kpis", "service dependencies", "glass tables"],
        "excludes": ["indexed events", "notable events", "episodes", "credentials", "instance ids"],
        "service_count": len(portable_services),
        "kpi_count": sum(len(item["kpis"]) for item in portable_services),
        "glass_tables": [item["title"] for item in glass],
        "files": ["services.json", *[f"glass-tables/{name}" for name in written]],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return manifest


def apply(out_dir: Path = EXPORT_DIR) -> dict:
    return write_export(_services(), _glass_tables(), out_dir)
