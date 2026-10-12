"""CLI: python -m itsi_lab <seed|apply-tree|ingest-samples|apply-kpis|ping>"""
from __future__ import annotations

import argparse
import json
import sys

from . import client, kpis, samples, tree


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


def cmd_seed(_args):
    print("== ping ==")
    cmd_ping(_args)
    print("== service tree ==")
    tree.apply()
    print("== sample data ==")
    samples.apply()
    print("== KPIs ==")
    kpis.apply()
    print("done. Open ITSI Service Analyzer and wait a few minutes for KPI searches.")


def main(argv=None):
    client.load_dotenv()
    parser = argparse.ArgumentParser(
        prog="python -m itsi_lab",
        description="Portable TAMM Splunk ITSI lab. Match services by title; no instance keys.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ping", help="Check management URL and auth")
    sub.add_parser("apply-tree", help="Create/update entities and the TAMM service tree")
    sub.add_parser("ingest-samples", help="Write 24h + last-3h degradation events")
    sub.add_parser("apply-kpis", help="Attach lab KPIs (thresholds + TVT) by service title")
    sub.add_parser("seed", help="ping + tree + samples + KPIs")
    args = parser.parse_args(argv)
    {
        "ping": cmd_ping,
        "apply-tree": cmd_apply_tree,
        "ingest-samples": cmd_ingest,
        "apply-kpis": cmd_apply_kpis,
        "seed": cmd_seed,
    }[args.cmd](args)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
