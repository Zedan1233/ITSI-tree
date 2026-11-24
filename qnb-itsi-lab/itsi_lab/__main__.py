"""CLI: python -m itsi_lab <seed|apply-tree|ingest-samples|apply-kpis|ping>"""
from __future__ import annotations

import argparse
import json
import sys

from . import client, demo, episodes, export_config, glass, kpis, samples, source_glass, tree


def cmd_ping(_args):
    _, info = client.request("GET", "/services/server/info", query={"output_mode": "json"})
    entry = (info or {}).get("entry") or [{}]
    content = entry[0].get("content") if isinstance(entry[0], dict) else {}
    print(
        json.dumps(
            {
                "mgmt": client.mgmt_url(),
                "version": content.get("version"),
                "serverName": content.get("serverName"),
                "auth": "token" if client._token() else "password",
            },
            indent=2,
        )
    )


def cmd_apply_tree(_args):
    tree.apply()


def cmd_ingest(_args):
    samples.apply()


def cmd_apply_kpis(_args):
    kpis.apply()


def cmd_apply_glass(_args):
    glass.apply()


def cmd_apply_episodes(_args):
    episodes.apply()


def cmd_apply_source_glass(_args):
    source_glass.apply()


def cmd_demo(_args):
    demo.apply()


def cmd_fill(_args):
    print("== 24h sample events ==")
    samples.apply()
    print("== KPI-aligned history for every catalog channel ==")
    demo.fill_history()
    print("KPI data ingested. Wait a few minutes for ITSI backfill, then refresh glass tables.")


def cmd_apply_config(_args):
    print("== service tree ==")
    tree.apply()
    print("== KPIs ==")
    kpis.apply()
    print("== glass tables ==")
    glass.apply()
    source_glass.apply()
    print("configuration applied. No sample events were ingested.")


def cmd_export(_args):
    export_config.apply()


def cmd_seed(_args):
    print("== ping ==")
    cmd_ping(_args)
    print("== service tree ==")
    tree.apply()
    print("== sample data ==")
    samples.apply()
    print("== KPIs ==")
    kpis.apply()
    print("== glass tables ==")
    glass.apply()
    print("done. Open ITSI Service Analyzer / Glass Tables and wait a few minutes for KPI searches.")


def main(argv=None):
    client.load_dotenv()
    parser = argparse.ArgumentParser(
        prog="python -m itsi_lab",
        description="Portable QNB Splunk ITSI lab. Match services by title; no instance keys.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ping", help="Check management URL and auth")
    sub.add_parser("apply-tree", help="Create/update entities and the QNB service tree")
    sub.add_parser("ingest-samples", help="Write 24h + last-3h degradation events")
    sub.add_parser("apply-kpis", help="Attach lab KPIs (thresholds + TVT) by service title")
    sub.add_parser("apply-glass", help="Create/update QNB executive and operations glass tables")
    sub.add_parser("apply-episodes", help="Open Episode Review notables for PTF, Database, Infra")
    sub.add_parser("apply-source-glass", help="Create the business and infrastructure source glass tables")
    sub.add_parser("apply-config", help="Apply the service tree, KPIs, and glass tables without sample data")
    sub.add_parser("export", help="Write services, KPIs, and glass tables to export/ without event data")
    sub.add_parser("seed", help="ping + tree + samples + KPIs + glass table")
    sub.add_parser("demo", help="Mixed leaf KPI data for the next 3 hours, plus an episode on each leaf")
    sub.add_parser("fill", help="Write 24h of events across every KPI channel for the tree and glass tables")
    args = parser.parse_args(argv)
    {
        "ping": cmd_ping,
        "apply-tree": cmd_apply_tree,
        "ingest-samples": cmd_ingest,
        "apply-kpis": cmd_apply_kpis,
        "apply-glass": cmd_apply_glass,
        "apply-episodes": cmd_apply_episodes,
        "apply-source-glass": cmd_apply_source_glass,
        "apply-config": cmd_apply_config,
        "export": cmd_export,
        "seed": cmd_seed,
        "demo": cmd_demo,
        "fill": cmd_fill,
    }[args.cmd](args)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
