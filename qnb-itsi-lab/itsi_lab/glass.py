"""ITSI glass tables on the Infrastructure & SaaS frame, bound to the service tree."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from urllib.parse import quote, urlencode

from . import client

TITLE = "QNB Business & digital services"
ASSET_DIR = Path(__file__).resolve().parent.parent / "assets"

# White page, off-white tiles, cream nested tiles.
NAVY_DEEP = "#FFFFFF"
NAVY = "#F8F6F2"
CARD = "#F7F3E8"
ROW = "#F1E8D4"
TEXT = "#1B1D21"
MUTED = "#6E5A3A"
CYAN = "#92722A"
GREEN = "#4F6B12"
AMBER = "#92722A"
AMBER_BG = "#F7F3E8"
LINE = "#C4B48A"
EPISODE_BG = "#F8F6F2"
EPISODE_ROW = "#F7F3E8"
EPISODE_HEADER = "#F1E8D4"


def asset_data_uri(filename: str, media_type: str) -> str:
    payload = base64.b64encode((ASSET_DIR / filename).read_bytes()).decode("ascii")
    return f"data:{media_type};base64,{payload}"

JOURNEY_SERVICES = [
    "Apply for Credit Card",
    "Apply for Personal Loan",
]

# Detail-panel dependency map: label -> live service title
DEPENDENCIES = [
    ("QNB app", "RUM"),
    ("Apply for Credit Card application", "APM"),
    ("Apply for Personal Loan application", "APM (Apply for Personal Loan)"),
    ("Identity", "Auth Provider"),
    ("Receipt & confirmation", "Feedback"),
]

FOCUS = "Apply for Credit Card"

# Glass-table tile -> (service title, KPI title on that service)
GLASS_METRICS = {
    "Call-center calls": ("Call Center", "Call-center calls"),
    "Social media posts": ("Social Media", "Social media posts"),
    "Login Success Rate": ("Auth Provider", "Login Success Rate"),
    "Completion rate": ("Apply for Credit Card", "Completion rate"),
    "Response time": ("APM", "APM response time"),
    "Incomplete applications": ("Apply for Credit Card", "Incomplete applications"),
    "Calls about this service": ("Apply for Credit Card", "Calls about this service"),
    "Posts about this service": ("Apply for Credit Card", "Posts about this service"),
}

SAMPLE_PREFIX = (
    'index={index} sourcetype={sourcetype} '
    '| rex field=_raw "^\\S+ \\S+ (?<json>.+)$" '
    "| spath input=json "
)


def _sample(extra: str = "") -> str:
    import os

    q = SAMPLE_PREFIX.format(
        index=os.environ.get("TAMM_SAMPLE_INDEX", "tamm_feedback"),
        sourcetype=os.environ.get("TAMM_SAMPLE_SOURCETYPE", "tamm:feedback"),
    )
    return q + extra


def resolve_services(titles: list[str]) -> dict:
    out = {}
    for title in titles:
        found = client.find_by_title("service", title)
        if not found:
            print(f"glass: service not found: {title}")
            continue
        shkpi = client.health_kpi_key(found) or f"SHKPI-{found['_key']}"
        out[title] = {"_key": found["_key"], "shkpi": shkpi, "title": title}
    return out


def find_kpi(service_title: str, kpi_title: str) -> dict | None:
    found = client.find_by_title("service", service_title)
    if not found:
        print(f"glass: service not found for KPI {kpi_title}: {service_title}")
        return None
    svc = client.get_service(found["_key"])
    for kpi in svc.get("kpis") or []:
        if kpi.get("title") == kpi_title:
            return {
                "kpi": kpi["_key"],
                "service": svc["_key"],
                "service_title": service_title,
                "name": f"{service_title} - {kpi_title}",
            }
    print(f"glass: KPI not found: {service_title} / {kpi_title}")
    return None


def resolve_metrics() -> dict:
    out = {}
    for label, (service_title, kpi_title) in GLASS_METRICS.items():
        info = find_kpi(service_title, kpi_title)
        if info:
            out[label] = info
    return out


class Builder:
    def __init__(self):
        self.viz = {}
        self.ds = {}
        self.struct = []
        self.n = 0

    def _id(self, prefix: str) -> str:
        self.n += 1
        return f"{prefix}_{self.n:03d}"

    def place(self, vid: str, x: int, y: int, w: int, h: int):
        self.struct.append({"item": vid, "type": "block", "position": {"x": x, "y": y, "w": w, "h": h}})

    def rect(self, x, y, w, h, fill, rx=10, stroke=None, stroke_width=0, opacity=None):
        vid = self._id("viz")
        options = {
            "fillColor": fill,
            "strokeWidth": stroke_width,
            "rx": rx,
            "ry": rx,
            "strokeColor": fill if stroke is None else stroke,
        }
        if opacity is not None:
            options["fillOpacity"] = opacity
        self.viz[vid] = {
            "type": "splunk.rectangle",
            "options": options,
        }
        self.place(vid, x, y, w, h)
        return vid

    def md(self, x, y, w, h, text, color=TEXT, size=16):
        vid = self._id("viz")
        self.viz[vid] = {
            "type": "splunk.markdown",
            "options": {
                "markdown": text,
                "fontColor": color,
                "color": color,
                "backgroundColor": "transparent",
                "fontSize": "custom",
                "customFontSize": size,
            },
        }
        self.place(vid, x, y, w, h)
        return vid

    def image(self, x, y, w, h, src, title=""):
        vid = self._id("viz")
        self.viz[vid] = {
            "type": "splunk.image",
            "options": {
                "src": src,
                "preserveAspectRatio": True,
                "title": title,
            },
        }
        self.place(vid, x, y, w, h)
        return vid

    def kpi_ds(self, name: str, kpi_id: str, service_id: str) -> str:
        did = self._id("ds")
        self.ds[did] = {
            "type": "ds.search",
            "name": name,
            "options": {
                "query": (
                    f"`get_full_itsi_summary_kpi({kpi_id})` `service_level_kpi_only` "
                    "| timechart cont=false latest(alert_value) AS alert_value, "
                    "latest(alert_color) AS alert_color"
                )
            },
            "meta": {"kpiID": kpi_id, "serviceID": service_id},
        }
        return did

    def search_ds(self, name: str, query: str, earliest: str | None = None, latest: str | None = None) -> str:
        did = self._id("ds")
        opts = {"query": query}
        if earliest or latest:
            opts["queryParameters"] = {
                "earliest": earliest or "$global_time.earliest$",
                "latest": latest or "$global_time.latest$",
            }
        self.ds[did] = {"type": "ds.search", "name": name, "options": opts}
        return did

    def table(self, x, y, w, h, dsid, *, bg=NAVY, drill=None, header_bg=None, row_colors=None):
        vid = self._id("viz")
        options = {
            "backgroundColor": bg,
            "showInternalFields": False,
            "showRowNumbers": False,
            "headerVisibility": "fixed",
            "count": 8,
        }
        if header_bg:
            options["headerBackgroundColor"] = header_bg
            options["headerColor"] = MUTED
        if row_colors:
            options["tableFormat"] = {
                "rowBackgroundColors": row_colors,
                "rowColors": [TEXT],
            }
        viz = {
            "type": "splunk.table",
            "dataSources": {"primary": dsid},
            "options": options,
        }
        if drill:
            viz["eventHandlers"] = [
                {"type": "drilldown.customUrl", "options": {"url": drill, "newTab": True}}
            ]
        self.viz[vid] = viz
        self.place(vid, x, y, w, h)
        return vid

    def single(self, x, y, w, h, dsid, *, unit="", unit_before=False, font=36, bg="transparent", drill=None, kpi_color=True, color=TEXT):
        vid = self._id("viz")
        viz = {
            "type": "splunk.singlevalue",
            "dataSources": {"primary": dsid},
            "options": {
                "backgroundColor": bg,
                "majorColor": "> primary | seriesByName(\"alert_color\") | lastPoint()" if kpi_color else color,
                "sparklineDisplay": "off",
                "trendDisplay": "off",
                "showSparklineTooltip": False,
                "unit": unit,
                "unitPosition": "before" if unit_before else "after",
                "useThousandSeparators": True,
                "majorFontSize": font,
                "sparklineValues": "> primary | seriesByName(\"alert_value\")",
            },
        }
        if drill:
            viz["eventHandlers"] = [
                {"type": "drilldown.customUrl", "options": {"url": drill, "newTab": True}}
            ]
        self.viz[vid] = viz
        self.place(vid, x, y, w, h)
        return vid

    def definition(
        self,
        title: str,
        description: str,
        *,
        background: str | None = None,
        width: int = 1920,
        height: int = 1080,
    ) -> dict:
        return {
            "title": title,
            "description": description,
            "inputs": {
                "input_global_refresh_rate": {
                    "dataSources": {},
                    "options": {
                        "defaultValue": "60s",
                        "items": [
                            {"label": "1 Minute", "value": "60s"},
                            {"label": "5 Minutes", "value": "300s"},
                            {"label": "30 Minutes", "value": "1800s"},
                        ],
                        "token": "global_refresh_rate",
                    },
                    "title": "Global Refresh Rate",
                    "type": "input.dropdown",
                },
                "input_global_trp": {
                    "dataSources": {},
                    "options": {"defaultValue": "-24h,now", "token": "global_time"},
                    "title": "Global Time Range",
                    "type": "input.timerange",
                },
            },
            "defaults": {
                "dataSources": {
                    "ds.search": {
                        "options": {
                            "queryParameters": {
                                "earliest": "$global_time.earliest$",
                                "latest": "$global_time.latest$",
                            },
                            "refresh": "$global_refresh_rate$",
                            "refreshType": "delay",
                        }
                    }
                }
            },
            "visualizations": self.viz,
            "dataSources": self.ds,
            "layout": {
                "tabs": {"items": [{"layoutId": "layout_1", "label": "QNB"}]},
                "layoutDefinitions": {
                    "layout_1": {
                        "type": "absolute",
                        "options": {
                            "backgroundColor": NAVY_DEEP if background is None else background,
                            "width": width,
                            "height": height,
                            "display": "auto-scale",
                        },
                        "structure": self.struct,
                    }
                },
                "globalInputs": ["input_global_trp", "input_global_refresh_rate"],
                "options": {"showTitleAndDescription": False, "display": "auto-scale"},
            },
        }


def _web_base() -> str:
    """Absolute web origin when SPLUNK_WEB_URL is set; otherwise a host-relative ITSI path."""
    return os.environ.get("SPLUNK_WEB_URL", "").strip().rstrip("/")


def service_link(service_id: str, title: str) -> str:
    """Open the service in ITSI Service Analyzer, matching the working Teams drilldown."""
    web = _web_base()
    query = urlencode(
        {
            "earliest": "-24h@h",
            "latest": "now",
            "view": "standard",
            "viewType": "service_topology",
            "kpi": "",
            "source": "",
            "service": title,
            "serviceId": service_id,
            "sidePanelTab": "kpis-and-episodes",
        },
        quote_via=quote,
    )
    return f"{web}/en-US/app/itsi/homeview?{query}"


def episode_review_link() -> str:
    web = _web_base()
    return f"{web}/en-US/app/itsi/itsi_event_management"


def _analyzer(service_id: str, title: str) -> str:
    return service_link(service_id, title)


FRAME_WIDTH = 1600
FRAME_HEIGHT = 1000
TOP_XS = (32, 339, 646, 953, 1260)


def brand_header(b: Builder, title: str, subtitle: str) -> None:
    """Logo, watermark, title and subtitle shared by every glass table."""
    b.image(350, 300, 900, 236, asset_data_uri("qnb-logo-watermark.png", "image/png"), "QNB watermark")
    b.image(32, 8, 300, 79, asset_data_uri("qnb-logo.png", "image/png"), "QNB")
    b.md(350, 16, 1210, 32, title, TEXT, 26)
    b.md(350, 50, 1210, 22, subtitle, MUTED, 13)


def top_tile(b: Builder, index: int, label: str) -> int:
    x = TOP_XS[index]
    b.rect(x, 88, 291, 128, NAVY)
    b.md(x + 14, 98, 263, 28, label, MUTED, 12)
    return x


def column_panel(b: Builder, x: int, w: int, title: str, subtitle: str, height: int = 620) -> None:
    b.rect(x, 232, w, height, NAVY)
    b.md(x + 16, 244, w - 32, 28, title, TEXT, 18)
    b.md(x + 16, 276, w - 32, 22, subtitle, MUTED, 12)


def note_bar(b: Builder, text: str) -> None:
    b.rect(32, 868, 1536, 78, NAVY, rx=8, stroke=LINE, stroke_width=1)
    b.md(48, 882, 1504, 48, text, MUTED, 13)


def health_value(b: Builder, services: dict, title: str, x, y, w, h, font, bg, name: str | None = None):
    service = services.get(title)
    if not service:
        return
    ds = b.kpi_ds(name or f"{title} health", service["shkpi"], service["_key"])
    b.single(x, y, w, h, ds, font=font, bg=bg, drill=_analyzer(service["_key"], title))


def metric_value(b, metrics, label, x, y, w, h, font, bg, unit="", prefix=False):
    info = metrics.get(label)
    if not info:
        return
    ds = b.kpi_ds(info["name"], info["kpi"], info["service"])
    b.single(
        x,
        y,
        w,
        h,
        ds,
        unit=unit,
        unit_before=prefix,
        font=font,
        bg=bg,
        drill=_analyzer(info["service"], info.get("service_title") or label),
    )


def build(services: dict, metrics: dict | None = None) -> dict:
    metrics = metrics or {}
    b = Builder()
    brand_header(
        b,
        "Business & digital services",
        "Demand and service delivery on the QNB tree",
    )
    tiles = [
        (0, "OVERALL HEALTH", "QNB", True, "", False),
        (1, "APPLY FOR CREDIT CARD", "Apply for Credit Card", True, "", False),
        (2, "APPLY FOR PERSONAL LOAN", "Apply for Personal Loan", True, "", False),
        (3, "COMPLETION RATE", "Completion rate", False, "%", False),
        (4, "CALL-CENTER CALLS", "Call-center calls", False, "", False),
    ]
    for index, label, key, health, unit, prefix in tiles:
        x = top_tile(b, index, label)
        if health:
            health_value(b, services, key, x + 12, 128, 267, 58, 30, NAVY)
        else:
            metric_value(b, metrics, key, x + 12, 128, 267, 58, 30, NAVY, unit, prefix)

    column_panel(b, 32, 730, "Service dependencies", "QNB app, applications, identity and confirmation")
    column_panel(b, 778, 380, "Apply for Credit Card", "Completion, response time, social posts and incomplete applications")
    column_panel(b, 1174, 394, "Business impact", "Auth success, calls and posts")

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
        ("Calls and posts", None, "", False),
        ("Posts about this service", "Posts about this service", "", False),
    ]
    for i, (title, key, unit, prefix) in enumerate(impacts):
        y = 318 + i * 160
        b.rect(1190, y, 362, 144, CARD, rx=8)
        b.md(1206, y + 16, 220, 28, title, TEXT, 15)
        if key is None:
            b.md(1206, y + 52, 180, 20, "Calls about this service", MUTED, 11)
            metric_value(b, metrics, "Calls about this service", 1206, y + 74, 160, 52, 22, CARD)
            b.md(1388, y + 52, 150, 20, "Posts about this service", MUTED, 11)
            metric_value(b, metrics, "Posts about this service", 1388, y + 74, 148, 52, 22, CARD)
        else:
            b.md(1206, y + 48, 210, 22, key, MUTED, 12)
            metric_value(b, metrics, key, 1410, y + 28, 124, 80, 24, CARD, unit, prefix)

    note_bar(
        b,
        "Scores are live ITSI service health from the QNB tree.",
    )
    return b.definition(
        TITLE,
        "Executive QNB glass table bound to the ITSI service tree.",
        background=NAVY_DEEP,
        width=FRAME_WIDTH,
        height=FRAME_HEIGHT,
    )


def upsert_glass_table(title: str, description: str, definition: dict) -> str:
    payload = {
        "object_type": "glass_table",
        "title": title,
        "description": description,
        "gt_version": "beta",
        "definition": definition,
        "_owner": "admin",
        "_user": "admin",
        "acl": {
            "owner": "admin",
            "perms": {"read": ["*"], "write": ["*"]},
            "sharing": "app",
        },
    }
    existing = None
    _, tables = client.request(
        "GET",
        "/servicesNS/nobody/SA-ITOA/itoa_interface/glass_table",
        query={"fields": "title,_key"},
    )
    matches = [g for g in (tables or []) if isinstance(g, dict) and g.get("title") == title]
    if matches:
        existing = matches[0]
        for extra in matches[1:]:
            try:
                client.request(
                    "DELETE",
                    f"/servicesNS/nobody/SA-ITOA/itoa_interface/glass_table/{extra['_key']}",
                )
                print(f"removed duplicate glass table {extra['_key']}")
            except RuntimeError as exc:
                print(f"duplicate delete skipped: {exc}")
    if existing:
        client.request(
            "POST",
            f"/servicesNS/nobody/SA-ITOA/itoa_interface/glass_table/{existing['_key']}",
            json_body=payload,
            query={"is_partial_data": "1"},
        )
        key = existing["_key"]
        print(f"updated glass table {title} {key}")
        return key
    _, body = client.request(
        "POST",
        "/servicesNS/nobody/SA-ITOA/itoa_interface/glass_table",
        json_body=payload,
    )
    key = body.get("_key") if isinstance(body, dict) else body
    print(f"created glass table {title} {key}")
    return key


def apply_executive():
    titles = [
        "QNB",
        FOCUS,
        *JOURNEY_SERVICES,
        *[t for _, t in DEPENDENCIES],
        "Call Center",
        "Social Media",
        "Auth Provider",
    ]
    services = resolve_services(list(dict.fromkeys(titles)))
    metrics = resolve_metrics()
    definition = build(services, metrics)
    key = upsert_glass_table(
        TITLE,
        "Executive view of demand and service delivery. Health scores are the live ITSI Service Health Scores from the QNB service tree.",
        definition,
    )
    print(json.dumps({"title": TITLE, "_key": key, "bound_services": sorted(services)}, indent=2))
    return key


def apply():
    from . import glass_ops

    exec_key = apply_executive()
    ops_key = glass_ops.apply()
    return {"executive": exec_key, "operations": ops_key}
