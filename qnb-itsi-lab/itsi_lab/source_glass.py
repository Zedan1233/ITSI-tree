"""Business and infrastructure glass tables, bound to the service tree."""
from __future__ import annotations

from .glass import (
    CARD,
    FRAME_HEIGHT,
    FRAME_WIDTH,
    MUTED,
    NAVY,
    TEXT,
    Builder,
    brand_header,
    column_panel,
    find_kpi,
    health_value,
    metric_value,
    note_bar,
    resolve_services,
    top_tile,
    upsert_glass_table,
)

BUSINESS_TITLE = "QNB | Business and digital service health"
INFRA_TITLE = "QNB | Infrastructure and SaaS health"

BUSINESS_BG = "#FFFFFF"
INFRA_BG = "#FFFFFF"

BUSINESS_SERVICES = [
    "Apply for Credit Card",
    "Apply for Personal Loan",
]
BUSINESS_METRICS = [
    ("Call-center calls", "Call Center", "Call-center calls"),
    ("Social media posts", "Social Media", "Social media posts"),
    ("Login Success Rate", "Auth Provider", "Login Success Rate"),
    ("App visitors", "RUM", "App visitors"),
    ("Completion rate", "Apply for Credit Card", "Completion rate"),
    ("Response time", "APM", "APM response time"),
    ("Incomplete applications", "Apply for Credit Card", "Incomplete applications"),
    ("Calls about this service", "Apply for Credit Card", "Calls about this service"),
    ("Posts about this service", "Apply for Credit Card", "Posts about this service"),
]
DEPENDENCIES = [
    ("QNB app", "RUM"),
    ("Apply for Credit Card application", "APM"),
    ("Apply for Personal Loan application", "APM (Apply for Personal Loan)"),
    ("Identity", "Auth Provider"),
    ("Receipt & confirmation", "Feedback"),
]

INFRA_HEALTH = [
    "Infrastructure Observability",
    "Network",
    "Cisco switches",
    "Network NetFlow",
    "Packet inspection",
    "Cisco firewall",
    "SD-WAN",
    "PowerMax arrays",
    "Microsoft Teams",
    "Office 365",
    "Cisco Webex",
    "Storage",
    "SaaS services",
]
INFRA_METRICS = [
    ("Critical alerts", "Infrastructure Observability", "Critical alerts"),
    ("Network availability", "Network", "Network availability"),
    ("Worst path packet loss", "SD-WAN", "Worst path packet loss"),
    ("PowerMax capacity", "PowerMax arrays", "PowerMax capacity"),
    ("PowerMax write latency", "PowerMax arrays", "PowerMax write latency"),
    ("Days to 80 percent", "PowerMax arrays", "Days to 80 percent"),
    ("Switch availability", "Cisco switches", "Switch availability"),
    ("NetFlow throughput", "Network NetFlow", "NetFlow throughput"),
    ("Packet inspection rate", "Packet inspection", "Packet inspection rate"),
    ("Firewall cluster health", "Cisco firewall", "Firewall cluster health"),
    ("Teams successful calls", "Microsoft Teams", "Teams successful calls"),
    ("Active incidents", "Office 365", "Active incidents"),
    ("Webex join success", "Cisco Webex", "Webex join success"),
    ("Storage capacity", "Storage", "Storage capacity"),
]


def _metrics(spec):
    out = {}
    for label, service, kpi in spec:
        info = find_kpi(service, kpi)
        if info:
            info["service_title"] = service
            out[label] = info
    return out


def build_business(services: dict, metrics: dict | None = None) -> dict:
    metrics = metrics or {}
    b = Builder()
    brand_header(
        b,
        "Business & digital service health",
        "Live ITSI service health and KPIs from the QNB tree",
    )
    tiles = [
        (0, "APPLY FOR CREDIT CARD", "Apply for Credit Card", True, "", False),
        (1, "APPLY FOR PERSONAL LOAN", "Apply for Personal Loan", True, "", False),
        (2, "CALL-CENTER CALLS", "Call-center calls", False, "", False),
        (3, "COMPLETION RATE", "Completion rate", False, "%", False),
        (4, "APP VISITORS", "App visitors", False, "", False),
    ]
    for index, label, key, health, unit, prefix in tiles:
        x = top_tile(b, index, label)
        if health:
            health_value(b, services, key, x + 12, 128, 267, 58, 30, NAVY)
        else:
            metric_value(b, metrics, key, x + 12, 128, 267, 58, 30, NAVY, unit, prefix)

    column_panel(b, 32, 730, "Service dependencies", "QNB app, applications, identity and confirmation")
    column_panel(b, 778, 380, "Apply for Credit Card", "Completion, response time, social posts and incomplete applications")
    column_panel(b, 1174, 394, "Business impact", "Auth success, calls and posts about this service")

    for i, (label, title) in enumerate(DEPENDENCIES):
        y = 318 + i * 100
        b.rect(48, y, 698, 88, CARD, rx=8)
        b.md(64, y + 12, 430, 28, label, TEXT, 16)
        b.md(64, y + 46, 300, 22, title, MUTED, 12)
        health_value(b, services, title, 500, y + 14, 220, 60, 24, CARD, name=f"{title} dependency health")

    b.rect(794, 318, 348, 150, CARD, rx=8)
    b.md(808, 330, 320, 24, "Journey delivery", TEXT, 15)
    b.md(808, 362, 150, 20, "Completion rate", MUTED, 11)
    metric_value(b, metrics, "Completion rate", 808, 382, 150, 48, 22, CARD, "%")
    b.md(970, 362, 150, 20, "Response time", MUTED, 11)
    metric_value(b, metrics, "Response time", 970, 382, 150, 48, 22, CARD, "ms")

    b.rect(794, 484, 348, 150, CARD, rx=8)
    b.md(808, 496, 320, 24, "Demand on this service", TEXT, 15)
    b.md(808, 530, 150, 20, "Social media posts", MUTED, 11)
    metric_value(b, metrics, "Social media posts", 808, 552, 150, 48, 22, CARD)
    b.md(970, 530, 150, 20, "Incomplete applications", MUTED, 11)
    metric_value(b, metrics, "Incomplete applications", 970, 552, 150, 48, 22, CARD)

    impacts = [
        ("Login success", "Login Success Rate", "%", False),
        ("Calls about this service", "Calls about this service", "", False),
        ("Posts about this service", "Posts about this service", "", False),
    ]
    for i, (title, key, unit, prefix) in enumerate(impacts):
        y = 318 + i * 160
        b.rect(1190, y, 362, 144, CARD, rx=8)
        b.md(1206, y + 16, 220, 40, title, TEXT, 15)
        b.md(1206, y + 56, 190, 22, key, MUTED, 12)
        metric_value(b, metrics, key, 1410, y + 28, 124, 80, 24, CARD, unit, prefix)

    note_bar(b, "Scores and business figures are live KPIs on the QNB service tree. Open a score to inspect that service.")
    return b.definition(
        BUSINESS_TITLE,
        "Business and digital services glass table bound to the QNB ITSI service tree.",
        background=BUSINESS_BG,
        width=FRAME_WIDTH,
        height=FRAME_HEIGHT,
    )


def build_infrastructure(services: dict, metrics: dict | None = None) -> dict:
    metrics = metrics or {}
    b = Builder()
    brand_header(
        b,
        "Infrastructure & SaaS service health",
        "Network, storage and collaboration services on the QNB tree",
    )
    tops = [
        (0, "OVERALL HEALTH", "Infrastructure Observability", True, ""),
        (1, "NETWORK AVAILABILITY", "Network availability", False, "%"),
        (2, "CRITICAL ALERTS", "Critical alerts", False, ""),
        (3, "WORST PATH PACKET LOSS", "Worst path packet loss", False, "%"),
        (4, "POWERMAX CAPACITY", "PowerMax capacity", False, "%"),
    ]
    for index, label, key, health, unit in tops:
        x = top_tile(b, index, label)
        if health:
            health_value(b, services, key, x + 12, 128, 267, 58, 30, NAVY)
        else:
            metric_value(b, metrics, key, x + 12, 128, 267, 58, 30, NAVY, unit)

    column_panel(b, 32, 730, "Network operations", "Cisco switches, NetFlow, inspection, firewall and SD-WAN")
    column_panel(b, 778, 380, "Storage", "PowerMax capacity, latency and forecast")
    column_panel(b, 1174, 394, "SaaS services", "Teams, Office 365 and Webex")

    network = [
        ("Cisco switches", "Switch availability"),
        ("Network NetFlow", "NetFlow throughput"),
        ("Packet inspection", "Packet inspection rate"),
        ("Cisco firewall", "Firewall cluster health"),
        ("SD-WAN", "Worst path packet loss"),
    ]
    for i, (title, caption) in enumerate(network):
        y = 318 + i * 100
        b.rect(48, y, 698, 88, CARD, rx=8)
        b.md(64, y + 12, 430, 28, title, TEXT, 16)
        b.md(64, y + 46, 300, 22, caption, MUTED, 12)
        unit = "%" if caption not in ("NetFlow throughput", "Packet inspection rate") else "Gbps"
        metric_value(b, metrics, caption, 500, y + 14, 220, 60, 24, CARD, unit)

    b.rect(794, 318, 348, 150, CARD, rx=8)
    b.md(808, 330, 220, 28, "PowerMax arrays", TEXT, 15)
    b.md(808, 362, 150, 20, "Capacity", MUTED, 11)
    metric_value(b, metrics, "PowerMax capacity", 808, 382, 150, 48, 22, CARD, "%")
    b.md(970, 362, 150, 20, "Write latency", MUTED, 11)
    metric_value(b, metrics, "PowerMax write latency", 970, 382, 150, 48, 22, CARD, "ms")
    b.rect(794, 484, 348, 150, CARD, rx=8)
    b.md(808, 496, 220, 28, "Capacity forecast", TEXT, 15)
    b.md(808, 530, 220, 22, "Days to 80 percent", MUTED, 12)
    metric_value(b, metrics, "Days to 80 percent", 1024, 560, 100, 52, 24, CARD, "d")

    saas = [
        ("Microsoft Teams", "Teams successful calls"),
        ("Office 365", "Active incidents"),
        ("Cisco Webex", "Webex join success"),
    ]
    for i, (title, caption) in enumerate(saas):
        y = 318 + i * 160
        b.rect(1190, y, 362, 144, CARD, rx=8)
        b.md(1206, y + 16, 220, 28, title, TEXT, 15)
        b.md(1206, y + 48, 210, 22, caption, MUTED, 12)
        unit = "%" if "success" in caption or "calls" in caption else ""
        metric_value(b, metrics, caption, 1410, y + 28, 124, 80, 24, CARD, unit)

    note_bar(
        b,
        "Infrastructure children are Network, Storage and SaaS services. Each value is the live KPI named on the tile.",
    )
    return b.definition(
        INFRA_TITLE,
        "Infrastructure and SaaS glass table bound to the QNB ITSI service tree.",
        background=INFRA_BG,
        width=FRAME_WIDTH,
        height=FRAME_HEIGHT,
    )


def apply():
    business_titles = [
        "QNB",
        "RUM",
        *BUSINESS_SERVICES,
        *[title for _, title in DEPENDENCIES],
        "Call Center",
        "Social Media",
        "Auth Provider",
    ]
    business_services = resolve_services(list(dict.fromkeys(business_titles)))
    business_metrics = _metrics(BUSINESS_METRICS)
    business_key = upsert_glass_table(
        BUSINESS_TITLE,
        "Business and digital services view connected to the QNB service tree.",
        build_business(business_services, business_metrics),
    )
    infra_services = resolve_services(INFRA_HEALTH)
    infra_metrics = _metrics(INFRA_METRICS)
    infra_key = upsert_glass_table(
        INFRA_TITLE,
        "Infrastructure and SaaS view connected to the QNB service tree.",
        build_infrastructure(infra_services, infra_metrics),
    )
    print({"business": business_key, "infrastructure": infra_key})
    return {"business": business_key, "infrastructure": infra_key}
