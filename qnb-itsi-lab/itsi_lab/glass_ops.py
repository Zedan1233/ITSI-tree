"""Operations glass table: tree health, Apply for Credit Card KPIs, latest episodes."""
from __future__ import annotations

import json

from .glass import (
    AMBER,
    CARD,
    CYAN,
    EPISODE_BG,
    EPISODE_HEADER,
    EPISODE_ROW,
    FRAME_HEIGHT,
    FRAME_WIDTH,
    GREEN,
    LINE,
    MUTED,
    NAVY,
    NAVY_DEEP,
    TEXT,
    Builder,
    brand_header,
    column_panel,
    episode_review_link,
    find_kpi,
    health_value,
    metric_value,
    resolve_services,
    top_tile,
    upsert_glass_table,
)

TITLE = "QNB Operations & episodes"

MAIN_BRANCHES = [
    "QNB",
    "Apply for Credit Card",
    "Apply for Personal Loan",
    "Authentication",
    "Infrastructure Observability",
    "AI Agent Observability",
]

SHARED_NODES = [
    "Auth Provider",
]

PTF = "Apply for Credit Card"

PTF_KPIS = [
    ("Completion rate", "Apply for Credit Card", "Completion rate", "%"),
    ("Incomplete applications", "Apply for Credit Card", "Incomplete applications", ""),
    ("Calls about this service", "Apply for Credit Card", "Calls about this service", ""),
    ("Posts about this service", "Apply for Credit Card", "Posts about this service", ""),
]

PTF_CHILDREN = ["APM", "RUM", "SNOW", "Feedback"]

STATUS_COLORS = {
    "New": CYAN,
    "In Progress": AMBER,
    "Pending": MUTED,
    "Resolved": GREEN,
    "Closed": MUTED,
}

EPISODE_REVIEW = episode_review_link()


def episode_status_query(status_label: str) -> str:
    return (
        "| inputlookup itsi_notable_group_user_lookup "
        "| eval status_label=case("
        'status="1","New",status="2","In Progress",status="3","Pending",'
        'status="4","Resolved",status="5","Closed",true(),status) '
        f'| search status_label="{status_label}" '
        "| stats count as alert_value"
    )


def episode_table_query() -> str:
    return (
        "| inputlookup itsi_notable_group_user_lookup "
        "| rename _key as itsi_group_id "
        "| eval Status=case("
        'status="1","New",status="2","In Progress",status="3","Pending",'
        'status="4","Resolved",status="5","Closed",true(),status) '
        "| eval Severity=case("
        'severity="6","Critical",severity="5","High",severity="4","Medium",'
        'severity="3","Low",severity="2","Normal",severity="1","Info",true(),severity) '
        "| join type=left itsi_group_id ["
        "search index=itsi_grouped_alerts sourcetype=itsi_notable:group "
        "| stats latest(title) as Episode latest(service_name) as Service "
        "latest(_time) as last count as Events by itsi_group_id"
        "] "
        '| eval Updated=strftime(last,"%Y-%m-%d %H:%M") '
        "| eval Owner=owner "
        "| sort -last "
        "| table Episode Service Status Severity Owner Events Updated"
    )


def resolve_metrics() -> dict:
    out = {}
    for label, service_title, kpi_title, _unit in PTF_KPIS:
        info = find_kpi(service_title, kpi_title)
        if info:
            out[label] = info
    return out


def build(services: dict, metrics: dict | None = None) -> dict:
    metrics = metrics or {}
    b = Builder()
    brand_header(
        b,
        "Operations & episodes",
        "Tree health, Apply for Credit Card KPIs, and Episode Review status",
    )
    tiles = [
        (0, "OVERALL HEALTH", "QNB"),
        (1, "APPLY FOR CREDIT CARD", "Apply for Credit Card"),
        (2, "APPLY FOR PERSONAL LOAN", "Apply for Personal Loan"),
        (3, "AUTH PROVIDER", "Auth Provider"),
        (4, "AUTHENTICATION", "Authentication"),
    ]
    for index, label, title in tiles:
        x = top_tile(b, index, label)
        health_value(b, services, title, x + 12, 128, 267, 58, 30, NAVY)

    column_panel(b, 32, 730, "Journey children", "Application, experience, tickets and feedback", 400)
    column_panel(b, 778, 380, "Apply for Credit Card", "Completion, incomplete applications, calls and posts", 400)
    column_panel(b, 1174, 394, "Platform services", "Infrastructure, AI agents and Auth Provider", 400)

    for i, title in enumerate(PTF_CHILDREN):
        y = 312 + i * 62
        b.rect(48, y, 698, 56, CARD, rx=8)
        b.md(64, y + 6, 400, 22, title, TEXT, 15)
        b.md(64, y + 30, 280, 18, "Service health", MUTED, 11)
        health_value(b, services, title, 500, y + 4, 220, 48, 22, CARD, name=f"{title} child health")

    pairs = [
        (312, "Journey KPIs", ("Completion rate", "%"), ("Incomplete applications", "")),
        (468, "Feedback about this service", ("Calls about this service", ""), ("Posts about this service", "")),
    ]
    for y, title, left, right in pairs:
        b.rect(794, y, 348, 140, CARD, rx=8)
        b.md(808, y + 10, 320, 22, title, TEXT, 14)
        b.md(808, y + 38, 150, 18, left[0], MUTED, 11)
        metric_value(b, metrics, left[0], 808, y + 58, 150, 64, 20, CARD, left[1])
        b.md(970, y + 38, 150, 18, right[0], MUTED, 11)
        metric_value(b, metrics, right[0], 970, y + 58, 150, 64, 20, CARD, right[1])

    platforms = [
        "Infrastructure Observability",
        "AI Agent Observability",
        "Auth Provider",
        "Authentication",
    ]
    for i, title in enumerate(platforms):
        y = 312 + i * 78
        b.rect(1190, y, 362, 70, CARD, rx=8)
        b.md(1206, y + 8, 200, 54, title, TEXT, 14)
        health_value(b, services, title, 1410, y + 8, 126, 54, 20, CARD, name=f"{title} platform health")

    b.rect(32, 648, 1536, 312, NAVY, rx=8, stroke=LINE, stroke_width=1)
    b.md(48, 658, 420, 26, "Latest episodes", TEXT, 16)
    b.md(480, 662, 720, 20, "Current status from Episode Review", MUTED, 12)
    for i, (label, color) in enumerate(STATUS_COLORS.items()):
        x = 48 + i * 302
        b.rect(x, 692, 290, 52, CARD, rx=8)
        b.md(x + 12, 704, 150, 22, label, MUTED, 12)
        ds = b.search_ds(f"Episodes {label}", episode_status_query(label), earliest="-7d", latest="now")
        b.single(x + 160, 694, 118, 48, ds, font=18, bg=CARD, kpi_color=False, color=color, drill=EPISODE_REVIEW)
    ds_ep = b.search_ds("Latest episodes", episode_table_query(), earliest="-7d", latest="now")
    b.table(
        48,
        754,
        1504,
        160,
        ds_ep,
        bg=EPISODE_BG,
        header_bg=EPISODE_HEADER,
        row_colors=[EPISODE_BG, EPISODE_ROW],
        drill=EPISODE_REVIEW,
    )
    b.md(48, 922, 1504, 22, "Scores are live ITSI service health from the QNB tree. Episode status is the current notable-group status.", MUTED, 12)
    return b.definition(
        TITLE,
        "QNB operations: tree health, Apply for Credit Card KPIs, and latest episode status.",
        background=NAVY_DEEP,
        width=FRAME_WIDTH,
        height=FRAME_HEIGHT,
    )


def apply():
    titles = list(dict.fromkeys([*MAIN_BRANCHES, *SHARED_NODES, PTF, *PTF_CHILDREN]))
    services = resolve_services(titles)
    metrics = resolve_metrics()
    definition = build(services, metrics)
    key = upsert_glass_table(
        TITLE,
        "Operations view of QNB tree health, Apply for Credit Card KPIs, and the latest ITSI episodes with current status.",
        definition,
    )
    print(json.dumps({"title": TITLE, "_key": key, "bound_services": sorted(services)}, indent=2))
    return key
