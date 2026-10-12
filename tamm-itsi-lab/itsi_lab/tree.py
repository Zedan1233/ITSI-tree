"""Create or update the TAMM service tree on any ITSI instance (match by title)."""
from __future__ import annotations

import json
from pathlib import Path

from . import client

TREE_PATH = Path(__file__).resolve().parent.parent / "config" / "tree.json"


def load_tree():
    return json.loads(TREE_PATH.read_text())


def upsert_entity(title: str, role: str, parent: str | None):
    existing = client.find_by_title("entity", title)
    payload = {
        "title": title,
        "description": f"{role} under {parent or 'root'}",
        "object_type": "entity",
        "_type": "entity",
        "sec_grp": "default_itsi_security_group",
        "identifying_name": title,
        "host": [title],
        "itsi_entity_id": [title],
        "itsi_role": [role],
        "site": [parent or title],
        "identifier": {"fields": ["host", "itsi_entity_id"], "values": [title]},
        "informational": {"fields": ["itsi_role", "site"], "values": [role, parent or title]},
    }
    if existing:
        client.request(
            "POST",
            f"/servicesNS/nobody/SA-ITOA/itoa_interface/entity/{existing['_key']}",
            json_body=payload,
            query={"is_partial_data": "1"},
        )
        return existing["_key"]
    _, created = client.request("POST", "/servicesNS/nobody/SA-ITOA/itoa_interface/entity", json_body=payload)
    return created.get("_key") if isinstance(created, dict) else created


def create_or_get_service(title: str, role: str):
    existing = client.find_by_title("service", title)
    if existing:
        return client.get_service(existing["_key"])
    upsert_entity(title, role, None)
    _, created = client.request(
        "POST",
        "/servicesNS/nobody/SA-ITOA/itoa_interface/service",
        json_body={
            "title": title,
            "description": f"ITSI service {title}",
            "object_type": "service",
            "enabled": 1,
            "sec_grp": "default_itsi_security_group",
            "entity_rules": [
                {
                    "rule_condition": "AND",
                    "rule_items": [
                        {
                            "field": "title",
                            "rule_type": "matches",
                            "value": title,
                            "field_type": "title",
                        }
                    ],
                }
            ],
        },
    )
    key = created.get("_key") if isinstance(created, dict) else created
    return client.get_service(key)


def set_depends_on(parent_key: str, children: list[dict]):
    client.request(
        "POST",
        f"/servicesNS/nobody/SA-ITOA/itoa_interface/service/{parent_key}",
        json_body={"services_depends_on": children},
        query={"is_partial_data": "1"},
    )
    return client.get_service(parent_key)


def apply_node(node: dict, parent_title: str | None = None) -> dict:
    title = node["title"]
    role = node.get("role", "service")
    print(f"upsert service {title}", flush=True)
    upsert_entity(title, role, parent_title)
    svc = create_or_get_service(title, role)
    child_svcs = [apply_node(child, title) for child in node.get("children") or []]
    if child_svcs:
        svc = set_depends_on(svc["_key"], [client.dep(c) for c in child_svcs])
    return svc


def apply():
    tree = load_tree()
    root = apply_node(tree["root"])
    print(json.dumps({"root": root.get("title"), "_key": root.get("_key")}, indent=2))
    return root
