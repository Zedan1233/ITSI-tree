"""Attach lab KPIs by service title. Thresholds are written into the ITSI Web TVT spec."""
from __future__ import annotations

import json
import uuid

from . import client

SEVERITY = {
    "critical": ("critical", 6, "#B50101", "#E5A6A6"),
    "high": ("high", 5, "#F26A35", "#FBCBB9"),
    "medium": ("medium", 4, "#FCB64E", "#FEE6C1"),
    "low": ("low", 3, "#FFE98C", "#FFF4C5"),
    "normal": ("normal", 2, "#99D18B", "#DCEFD7"),
}


def _levels(pairs, metric_field, higher_better=False, gauge_max=None):
    levels = []
    for value, name in pairs:
        label, sval, color, light = SEVERITY[name]
        levels.append(
            {
                "thresholdValue": value,
                "severityLabel": label,
                "severityValue": sval,
                "severityColor": color,
                "severityColorLight": light,
                "dynamicParam": 0,
            }
        )
    if gauge_max is None:
        gauge_max = max(p[0] for p in pairs) * 1.5
    th = {
        "thresholdLevels": levels,
        "gaugeMax": gauge_max,
        "gaugeMin": 0,
        "isMaxStatic": False,
        "isMinStatic": True,
        "baseSeverityLabel": "critical" if higher_better else "normal",
        "baseSeverityValue": 6 if higher_better else 2,
        "baseSeverityColor": "#B50101" if higher_better else "#99D18B",
        "baseSeverityColorLight": "#E5A6A6" if higher_better else "#DCEFD7",
        "metricField": metric_field,
        "search": "",
        "renderBoundaryMin": 0,
        "renderBoundaryMax": gauge_max,
    }
    return th


def _kpi(title, channel, field, statop, unit, urgency, th, extra=""):
    index = os_index()
    sourcetype = os_sourcetype()
    extra_q = f" {extra}" if extra else ""
    base_search = (
        f"index={index} sourcetype={sourcetype} "
        f"| rex field=_raw \"^\\S+ \\S+ (?<json>.+)$\" "
        f"| spath input=json "
        f"| search channel={channel}{extra_q}"
    )
    entity_th = json.loads(json.dumps(th))
    tvt = {
        "policies": {
            "default_policy": {
                "title": "Default",
                "policy_type": "static",
                "time_blocks": [],
                "aggregate_thresholds": json.loads(json.dumps(th)),
                "entity_thresholds": json.loads(json.dumps(entity_th)),
            }
        }
    }
    return {
        "_key": str(uuid.uuid4()),
        "title": title,
        "type": "kpis",
        "search_type": "adhoc",
        "base_search": base_search,
        "threshold_field": field,
        "aggregate_statop": statop,
        "entity_statop": statop,
        "is_entity_breakdown": False,
        "is_service_entity_filter": False,
        "alert_period": "5",
        "alert_lag": "0",
        "search_alert_earliest": "5",
        "urgency": str(urgency),
        "unit": unit,
        "enabled": True,
        "fill_gaps": "last_available_value",
        "gap_severity": "unknown",
        "gap_severity_value": "-1",
        "gap_severity_color": "#CCCCCC",
        "gap_severity_color_light": "#EEEEEE",
        "backfill_enabled": True,
        "backfill_earliest_time": "-24h",
        "adaptive_thresholds_is_enabled": False,
        "time_variate_thresholds": False,
        "time_variate_thresholds_specification": tvt,
        "anomaly_detection_is_enabled": False,
        "alert_on": "both",
        "aggregate_thresholds": th,
        "entity_thresholds": entity_th,
        "datamodel": {"datamodel": "", "object": "", "owner_field": "", "field": ""},
        "datamodel_filter": [],
        "kpi_base_search": "",
        "source": "tamm_lab_sample",
    }


def os_index():
    import os

    return os.environ.get("TAMM_SAMPLE_INDEX", "tamm_feedback")


def os_sourcetype():
    import os

    return os.environ.get("TAMM_SAMPLE_SOURCETYPE", "tamm:feedback")


def worse(pairs, field, gauge=None):
    return _levels(pairs, field if field != "_time" else "count", False, gauge)


def better(pairs, field, gauge):
    return _levels(pairs, field, True, gauge)


def catalog():
    """KPIs keyed by exact ITSI service title."""
    return {
        "Call Center": [
            _kpi("Inbound Volume", "call_center", "_time", "count", "calls", 6, worse([(40, "low"), (55, "medium"), (70, "high"), (90, "critical")], "_time")),
            _kpi("Average Handle Time", "call_center", "handle_time_sec", "avg", "sec", 5, worse([(400, "low"), (500, "medium"), (600, "high"), (700, "critical")], "handle_time_sec"), "abandoned=0"),
            _kpi("Abandonment Rate", "call_center", "abandoned", "avg", "%", 8, worse([(6, "low"), (10, "medium"), (15, "high"), (20, "critical")], "abandoned")),
            _kpi("Repeat Contact Rate", "call_center", "repeat_contact", "avg", "%", 7, worse([(10, "low"), (15, "medium"), (22, "high"), (30, "critical")], "repeat_contact")),
            _kpi("Escalation Rate", "call_center", "escalated", "avg", "%", 8, worse([(4, "low"), (7, "medium"), (10, "high"), (15, "critical")], "escalated")),
        ],
        "Survey": [
            _kpi("CSAT", "survey", "csat", "avg", "score", 8, better([(0, "critical"), (2.5, "high"), (3.2, "medium"), (3.8, "low"), (4.2, "normal")], "csat", 5)),
            _kpi("CES", "survey", "ces", "avg", "score", 6, worse([(3.5, "low"), (4.2, "medium"), (5.0, "high"), (5.8, "critical")], "ces")),
            _kpi("Response Volume", "survey", "_time", "count", "responses", 3, worse([(25, "low"), (35, "medium"), (45, "high"), (60, "critical")], "_time")),
            _kpi("Thumbs Down Rate", "survey", "thumbs_down", "avg", "%", 7, worse([(10, "low"), (18, "medium"), (28, "high"), (40, "critical")], "thumbs_down")),
        ],
        "Social Media": [
            _kpi("Mention Volume", "social_media", "_time", "count", "mentions", 5, worse([(25, "low"), (35, "medium"), (45, "high"), (60, "critical")], "_time")),
            _kpi("Negative Sentiment", "social_media", "negative", "avg", "%", 7, worse([(25, "low"), (35, "medium"), (45, "high"), (55, "critical")], "negative")),
            _kpi("Viral Posts", "social_media", "viral", "avg", "%", 8, worse([(4, "low"), (8, "medium"), (12, "high"), (18, "critical")], "viral")),
            _kpi("Response SLA Breach", "social_media", "sla_breached", "avg", "%", 5, worse([(10, "low"), (18, "medium"), (28, "high"), (40, "critical")], "sla_breached")),
        ],
        "SNOW": [
            _kpi("Open P1/P2 Rate", "snow", "is_p1p2", "avg", "%", 11, worse([(12, "low"), (20, "medium"), (30, "high"), (40, "critical")], "is_p1p2"), "event_type=incident"),
            _kpi("MTTA", "snow", "mtta_min", "avg", "min", 7, worse([(12, "low"), (20, "medium"), (30, "high"), (40, "critical")], "mtta_min"), "event_type=incident"),
            _kpi("MTTR", "snow", "mttr_min", "avg", "min", 7, worse([(60, "low"), (90, "medium"), (120, "high"), (150, "critical")], "mttr_min"), "event_type=incident resolved=100"),
            _kpi("Aged Tickets", "snow", "aged", "avg", "%", 5, worse([(8, "low"), (14, "medium"), (20, "high"), (28, "critical")], "aged"), "event_type=incident"),
            _kpi("Change Failure Rate", "snow", "change_failed", "avg", "%", 6, worse([(8, "low"), (14, "medium"), (22, "high"), (30, "critical")], "change_failed"), "event_type=change"),
        ],
        "Revenue": [
            _kpi("Payment Success Rate", "revenue", "success", "avg", "%", 11, better([(0, "critical"), (70, "high"), (80, "medium"), (90, "low"), (96, "normal")], "success", 100)),
            _kpi("Payment Failure Rate", "revenue", "failed", "avg", "%", 10, worse([(4, "low"), (8, "medium"), (12, "high"), (16, "critical")], "failed")),
            _kpi("Abandoned Checkout", "revenue", "abandoned", "avg", "%", 7, worse([(6, "low"), (10, "medium"), (14, "high"), (18, "critical")], "abandoned")),
            _kpi("Refund Rate", "revenue", "refund", "avg", "%", 4, worse([(3, "low"), (5, "medium"), (7, "high"), (10, "critical")], "refund")),
        ],
        "UAE Pass": [
            _kpi("Login Success Rate", "uaepass", "success", "avg", "%", 11, better([(0, "critical"), (80, "high"), (90, "medium"), (96, "low"), (99, "normal")], "success", 100)),
            _kpi("Auth P95", "uaepass", "latency_ms", "avg", "ms", 10, worse([(800, "low"), (1200, "medium"), (1800, "high"), (2400, "critical")], "latency_ms")),
            _kpi("SAML Error Rate", "uaepass", "saml_error", "avg", "%", 10, worse([(3, "low"), (6, "medium"), (10, "high"), (15, "critical")], "saml_error")),
            _kpi("MFA Failure Rate", "uaepass", "mfa_fail", "avg", "%", 6, worse([(4, "low"), (7, "medium"), (10, "high"), (14, "critical")], "mfa_fail")),
        ],
        "Authentication": [
            _kpi("Session Establish Rate", "authentication", "session_ok", "avg", "%", 11, better([(0, "critical"), (80, "high"), (90, "medium"), (96, "low"), (99, "normal")], "session_ok", 100)),
        ],
        "AppDynamics": [
            _kpi("Agent Ingest Healthy", "appdynamics", "ingest_healthy", "avg", "%", 8, better([(0, "critical"), (80, "high"), (90, "medium"), (95, "low"), (98, "normal")], "ingest_healthy", 100)),
            _kpi("BT Error Rate", "appdynamics", "bt_error_rate", "avg", "%", 10, worse([(1, "low"), (2, "medium"), (4, "high"), (6, "critical")], "bt_error_rate")),
            _kpi("Open Problems", "appdynamics", "open_problems", "avg", "count", 9, worse([(2, "low"), (4, "medium"), (8, "high"), (12, "critical")], "open_problems")),
            _kpi("Dropped Agents", "appdynamics", "dropped_agents", "avg", "count", 6, worse([(1, "low"), (2, "medium"), (4, "high"), (6, "critical")], "dropped_agents")),
        ],
        "Azure": [
            _kpi("Unhealthy Resources", "azure", "unhealthy_resources", "avg", "count", 8, worse([(1, "low"), (2, "medium"), (4, "high"), (6, "critical")], "unhealthy_resources")),
            _kpi("App Service Availability", "azure", "appservice_avail", "avg", "%", 10, better([(0, "critical"), (90, "high"), (95, "medium"), (98, "low"), (99.5, "normal")], "appservice_avail", 100)),
            _kpi("Pipeline Failures", "azure", "pipeline_fail", "avg", "%", 5, worse([(5, "low"), (10, "medium"), (16, "high"), (22, "critical")], "pipeline_fail")),
            _kpi("Monitor Ingest Delay", "azure", "ingest_delay_sec", "avg", "sec", 6, worse([(20, "low"), (40, "medium"), (80, "high"), (120, "critical")], "ingest_delay_sec")),
        ],
        "Kubernetes": [
            _kpi("CrashLooping Pods", "kubernetes", "crashloop_pct", "avg", "%", 10, worse([(2, "low"), (5, "medium"), (10, "high"), (15, "critical")], "crashloop_pct")),
            _kpi("Node NotReady", "kubernetes", "node_notready", "avg", "count", 11, worse([(1, "low"), (1.5, "medium"), (2, "high"), (3, "critical")], "node_notready")),
            _kpi("Ingress 5xx", "kubernetes", "ingress_5xx", "avg", "%", 10, worse([(1, "low"), (2, "medium"), (4, "high"), (7, "critical")], "ingress_5xx")),
            _kpi("Pending Pods", "kubernetes", "pending_pods", "avg", "count", 6, worse([(2, "low"), (4, "medium"), (8, "high"), (12, "critical")], "pending_pods")),
        ],
        "Database": [
            _kpi("Query P95", "database", "query_p95_ms", "avg", "ms", 11, worse([(150, "low"), (300, "medium"), (800, "high"), (1400, "critical")], "query_p95_ms")),
            _kpi("Lock Waits", "database", "lock_wait_ms", "avg", "ms", 9, worse([(40, "low"), (80, "medium"), (200, "high"), (350, "critical")], "lock_wait_ms")),
            _kpi("Connection Errors", "database", "conn_error_rate", "avg", "%", 10, worse([(1, "low"), (3, "medium"), (6, "high"), (10, "critical")], "conn_error_rate")),
            _kpi("Connection Saturation", "database", "conn_sat_pct", "avg", "%", 8, worse([(70, "low"), (80, "medium"), (88, "high"), (93, "critical")], "conn_sat_pct")),
            _kpi("Replication Lag", "database", "repl_lag_sec", "avg", "sec", 7, worse([(5, "low"), (10, "medium"), (20, "high"), (35, "critical")], "repl_lag_sec")),
            _kpi("Storage Used", "database", "storage_pct", "avg", "%", 4, worse([(75, "low"), (82, "medium"), (88, "high"), (92, "critical")], "storage_pct")),
        ],
        "AD-Connect Endpoints": [
            _kpi("Endpoint Availability", "ad_connect", "availability", "avg", "%", 11, better([(0, "critical"), (90, "high"), (95, "medium"), (98, "low"), (99.5, "normal")], "availability", 100)),
            _kpi("Handshake Failures", "ad_connect", "handshake_fail", "avg", "%", 10, worse([(2, "low"), (5, "medium"), (10, "high"), (16, "critical")], "handshake_fail")),
            _kpi("Consumer Error Rate", "ad_connect", "consumer_error", "avg", "%", 8, worse([(3, "low"), (6, "medium"), (10, "high"), (15, "critical")], "consumer_error")),
            _kpi("Certificate Days Left", "ad_connect", "cert_days_left", "avg", "days", 5, better([(0, "critical"), (7, "high"), (14, "medium"), (30, "low"), (60, "normal")], "cert_days_left", 120)),
        ],
    }


def attach_to_service(title: str, new_kpis: list[dict]):
    found = client.find_by_title("service", title)
    if not found:
        print(f"skip KPIs; service not found: {title}")
        return
    svc = client.get_service(found["_key"])
    titles = {k["title"] for k in new_kpis}
    merged = [
        k
        for k in (svc.get("kpis") or [])
        if k.get("type") == "service_health" or k.get("title") not in titles
    ]
    merged.extend(new_kpis)
    client.request(
        "POST",
        f"/servicesNS/nobody/SA-ITOA/itoa_interface/service/{found['_key']}",
        json_body={"kpis": merged},
        query={"is_partial_data": "1"},
    )
    print(f"KPIs on {title}: {[k['title'] for k in new_kpis]}")


def apply():
    for title, kpis in catalog().items():
        attach_to_service(title, kpis)
