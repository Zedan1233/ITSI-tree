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
        f'| search channel="{channel}"{extra_q}'
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
        "source": "qnb_lab_sample",
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


LEAF_SERVICES = [
    ("APM", "svc_apm", "apm"),
    ("Card eligibility service", "card_eligibility", "eligibility"),
    ("Card printing service", "card_printing", "printing"),
    ("APM (Apply for Personal Loan)", "svc_apm_loan", "apm"),
    ("RUM (Apply for Personal Loan)", "svc_rum_loan", "rum"),
    ("SNOW (Apply for Personal Loan)", "svc_snow_loan", "snow"),
    ("Call Center (Apply for Personal Loan)", "svc_calls_loan", "calls"),
    ("Survey (Apply for Personal Loan)", "svc_survey_loan", "survey"),
    ("Social Media (Apply for Personal Loan)", "svc_social_loan", "social"),
]


def _leaf_builders():
    return {
        "apm": lambda c: [
            _kpi("APM error rate", c, "error_pct", "avg", "%", 9, worse([(1, "low"), (2, "medium"), (4, "high"), (8, "critical")], "error_pct")),
            _kpi("APM response time", c, "response_ms", "avg", "ms", 8, worse([(400, "low"), (800, "medium"), (1500, "high"), (2500, "critical")], "response_ms")),
            _kpi("APM throughput", c, "throughput", "avg", "rpm", 4, better([(0, "critical"), (40, "high"), (70, "medium"), (100, "low"), (130, "normal")], "throughput", 250)),
        ],
        "rum": lambda c: [
            _kpi("Page visitors", c, "visitors", "avg", "users", 4, better([(0, "critical"), (500, "high"), (1000, "medium"), (1600, "low"), (2200, "normal")], "visitors", 4000)),
            _kpi("Page load", c, "page_load_ms", "avg", "ms", 7, worse([(1500, "low"), (2500, "medium"), (4000, "high"), (6000, "critical")], "page_load_ms")),
            _kpi("Client error rate", c, "client_error_pct", "avg", "%", 8, worse([(1, "low"), (2, "medium"), (4, "high"), (8, "critical")], "client_error_pct")),
        ],
        "snow": lambda c: [
            _kpi("Open P1/P2 rate", c, "p1p2_pct", "avg", "%", 10, worse([(12, "low"), (20, "medium"), (30, "high"), (40, "critical")], "p1p2_pct")),
            _kpi("MTTR", c, "mttr_min", "avg", "min", 7, worse([(60, "low"), (90, "medium"), (120, "high"), (150, "critical")], "mttr_min")),
            _kpi("Aged tickets", c, "aged_pct", "avg", "%", 5, worse([(8, "low"), (14, "medium"), (20, "high"), (28, "critical")], "aged_pct")),
        ],
        "calls": lambda c: [
            _kpi("Calls", c, "calls", "avg", "calls", 6, worse([(6, "low"), (10, "medium"), (14, "high"), (20, "critical")], "calls")),
            _kpi("Abandonment rate", c, "abandon_pct", "avg", "%", 8, worse([(6, "low"), (10, "medium"), (15, "high"), (20, "critical")], "abandon_pct")),
            _kpi("Average handle time", c, "handle_sec", "avg", "sec", 5, worse([(400, "low"), (500, "medium"), (600, "high"), (700, "critical")], "handle_sec")),
        ],
        "survey": lambda c: [
            _kpi("CSAT", c, "csat", "avg", "score", 8, better([(0, "critical"), (2.5, "high"), (3.2, "medium"), (3.8, "low"), (4.2, "normal")], "csat", 5)),
            _kpi("Responses", c, "responses", "avg", "responses", 3, worse([(15, "low"), (22, "medium"), (30, "high"), (40, "critical")], "responses")),
            _kpi("Thumbs down rate", c, "thumbs_down_pct", "avg", "%", 7, worse([(10, "low"), (18, "medium"), (28, "high"), (40, "critical")], "thumbs_down_pct")),
        ],
        "social": lambda c: [
            _kpi("Posts", c, "posts", "avg", "posts", 6, worse([(4, "low"), (7, "medium"), (10, "high"), (14, "critical")], "posts")),
            _kpi("Negative sentiment", c, "negative_pct", "avg", "%", 7, worse([(25, "low"), (35, "medium"), (45, "high"), (55, "critical")], "negative_pct")),
            _kpi("SLA breach", c, "sla_pct", "avg", "%", 5, worse([(10, "low"), (18, "medium"), (28, "high"), (40, "critical")], "sla_pct")),
        ],
        "revenue": lambda c: [
            _kpi("Payment success rate", c, "success_pct", "avg", "%", 10, better([(0, "critical"), (70, "high"), (80, "medium"), (90, "low"), (96, "normal")], "success_pct", 100)),
            _kpi("Payment failure rate", c, "failed_pct", "avg", "%", 9, worse([(4, "low"), (8, "medium"), (12, "high"), (16, "critical")], "failed_pct")),
            _kpi("Incomplete payments", c, "incomplete", "avg", "txns", 8, worse([(2, "low"), (4, "medium"), (6, "high"), (8, "critical")], "incomplete")),
        ],
        "judicial": lambda c: [
            _kpi("Case completion", c, "completion_pct", "avg", "%", 8, better([(0, "critical"), (70, "high"), (80, "medium"), (90, "low"), (95, "normal")], "completion_pct", 100)),
            _kpi("Hearing delay", c, "delay_min", "avg", "min", 6, worse([(20, "low"), (35, "medium"), (50, "high"), (70, "critical")], "delay_min")),
            _kpi("Open cases", c, "open_cases", "avg", "cases", 5, worse([(30, "low"), (45, "medium"), (60, "high"), (80, "critical")], "open_cases")),
        ],
        "health": lambda c: [
            _kpi("Appointment success", c, "success_pct", "avg", "%", 8, better([(0, "critical"), (75, "high"), (85, "medium"), (92, "low"), (96, "normal")], "success_pct", 100)),
            _kpi("Record lookup", c, "lookup_ms", "avg", "ms", 6, worse([(400, "low"), (800, "medium"), (1200, "high"), (2000, "critical")], "lookup_ms")),
            _kpi("Open referrals", c, "open_referrals", "avg", "referrals", 5, worse([(10, "low"), (15, "medium"), (20, "high"), (30, "critical")], "open_referrals")),
        ],
        "eligibility": lambda c: [
            _kpi("Eligibility approval rate", c, "approval_pct", "avg", "%", 10, better([(0, "critical"), (70, "high"), (80, "medium"), (90, "low"), (96, "normal")], "approval_pct", 100)),
            _kpi("Eligibility decision time", c, "decision_ms", "avg", "ms", 8, worse([(400, "low"), (800, "medium"), (1500, "high"), (2500, "critical")], "decision_ms")),
            _kpi("Eligibility error rate", c, "error_pct", "avg", "%", 9, worse([(1, "low"), (2, "medium"), (4, "high"), (8, "critical")], "error_pct")),
        ],
        "printing": lambda c: [
            _kpi("Print success rate", c, "success_pct", "avg", "%", 10, better([(0, "critical"), (80, "high"), (90, "medium"), (96, "low"), (99, "normal")], "success_pct", 100)),
            _kpi("Print fulfillment time", c, "fulfill_min", "avg", "min", 8, worse([(30, "low"), (60, "medium"), (120, "high"), (240, "critical")], "fulfill_min")),
            _kpi("Reprint rate", c, "reprint_pct", "avg", "%", 7, worse([(2, "low"), (4, "medium"), (8, "high"), (14, "critical")], "reprint_pct")),
        ],
    }


def leaf_kpis():
    """Sample KPIs for leaf services that have no lab KPIs of their own."""
    builders = _leaf_builders()
    return {title: builders[kind](channel) for title, channel, kind in LEAF_SERVICES}


def catalog():
    """KPIs keyed by exact ITSI service title."""
    data = {
        "Call Center": [
            _kpi("Call-center calls", "call_center", "_time", "count", "calls", 8, worse([(6, "low"), (10, "medium"), (14, "high"), (20, "critical")], "_time")),
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
            _kpi("Social media posts", "social_media", "_time", "count", "posts", 7, worse([(4, "low"), (7, "medium"), (10, "high"), (14, "critical")], "_time")),
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
        "Apply for Credit Card": [
            _kpi("Completion rate", "revenue", "success", "avg", "%", 11, better([(0, "critical"), (70, "high"), (80, "medium"), (90, "low"), (96, "normal")], "success", 100)),
            _kpi("Incomplete applications", "revenue", "_time", "count", "txns", 9, worse([(2, "low"), (4, "medium"), (6, "high"), (8, "critical")], "_time"), "(failed=100 OR abandoned=100)"),
            _kpi("Calls about this service", "call_center", "_time", "count", "calls", 8, worse([(6, "low"), (10, "medium"), (14, "high"), (20, "critical")], "_time")),
            _kpi("Posts about this service", "social_media", "_time", "count", "posts", 6, worse([(4, "low"), (7, "medium"), (10, "high"), (14, "critical")], "_time")),
        ],
        "Auth Provider": [
            _kpi("Login Success Rate", "auth_provider", "success", "avg", "%", 11, better([(0, "critical"), (80, "high"), (90, "medium"), (96, "low"), (99, "normal")], "success", 100)),
            _kpi("Auth P95", "auth_provider", "latency_ms", "avg", "ms", 10, worse([(800, "low"), (1200, "medium"), (1800, "high"), (2400, "critical")], "latency_ms")),
            _kpi("SAML Error Rate", "auth_provider", "saml_error", "avg", "%", 10, worse([(3, "low"), (6, "medium"), (10, "high"), (15, "critical")], "saml_error")),
            _kpi("MFA Failure Rate", "auth_provider", "mfa_fail", "avg", "%", 6, worse([(4, "low"), (7, "medium"), (10, "high"), (14, "critical")], "mfa_fail")),
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
        "RUM": [
            _kpi("App visitors", "app_visitors", "visitor_id", "dc", "users", 3, worse([(20, "low"), (40, "medium"), (80, "high"), (120, "critical")], "visitor_id", 200)),
        ],
        "Infrastructure Observability": [
            _kpi("Critical alerts", "infra_alert", "critical", "sum", "alerts", 9, worse([(1, "low"), (2, "medium"), (4, "high"), (6, "critical")], "critical")),
        ],
        "Network": [
            _kpi("Network availability", "switch", "availability", "avg", "%", 10, better([(0, "critical"), (90, "high"), (95, "medium"), (98, "low"), (99.5, "normal")], "availability", 100)),
        ],
        "Storage": [
            _kpi("Storage capacity", "powermax", "capacity_pct", "avg", "%", 7, worse([(78, "low"), (85, "medium"), (90, "high"), (95, "critical")], "capacity_pct", 100)),
        ],
        "Cisco switches": [
            _kpi("Switch availability", "switch", "availability", "avg", "%", 10, better([(0, "critical"), (90, "high"), (95, "medium"), (98, "low"), (99.5, "normal")], "availability", 100)),
            _kpi("Port use", "switch", "port_use", "avg", "%", 5, worse([(70, "low"), (80, "medium"), (88, "high"), (93, "critical")], "port_use", 100)),
            _kpi("Interface errors", "switch", "interface_errors", "avg", "errors", 6, worse([(5, "low"), (10, "medium"), (20, "high"), (40, "critical")], "interface_errors")),
        ],
        "Network NetFlow": [
            _kpi("NetFlow throughput", "netflow", "gbps", "avg", "Gbps", 6, better([(0, "critical"), (5, "high"), (8, "medium"), (12, "low"), (16, "normal")], "gbps", 40)),
            _kpi("Flows per minute", "netflow", "flows_per_min", "avg", "flows", 4, worse([(5000000, "low"), (6000000, "medium"), (8000000, "high"), (10000000, "critical")], "flows_per_min", 12000000)),
            _kpi("Flow anomalies", "netflow", "anomalies", "avg", "anomalies", 6, worse([(3, "low"), (5, "medium"), (8, "high"), (12, "critical")], "anomalies")),
        ],
        "Packet inspection": [
            _kpi("Packet inspection rate", "packet", "gbps", "avg", "Gbps", 6, better([(0, "critical"), (1, "high"), (2, "medium"), (3.5, "low"), (4.2, "normal")], "gbps", 12)),
            _kpi("Protocols inspected", "packet", "protocols", "avg", "protocols", 3, worse([(40, "low"), (50, "medium"), (60, "high"), (80, "critical")], "protocols", 100)),
            _kpi("Inspection degradations", "packet", "degradations", "avg", "events", 6, worse([(1, "low"), (2, "medium"), (4, "high"), (6, "critical")], "degradations")),
        ],
        "Cisco firewall": [
            _kpi("Firewall cluster health", "firewall", "health_pct", "avg", "%", 9, better([(0, "critical"), (80, "high"), (90, "medium"), (95, "low"), (98, "normal")], "health_pct", 100)),
            _kpi("Firewall nodes online", "firewall", "nodes_online", "avg", "nodes", 8, better([(0, "critical"), (10, "high"), (14, "medium"), (16, "low"), (18, "normal")], "nodes_online", 18)),
            _kpi("Connection utilization", "firewall", "connection_pct", "avg", "%", 6, worse([(60, "low"), (70, "medium"), (80, "high"), (90, "critical")], "connection_pct", 100)),
            _kpi("Firewall health alerts", "firewall", "health_alerts", "avg", "alerts", 7, worse([(1, "low"), (2, "medium"), (3, "high"), (5, "critical")], "health_alerts")),
        ],
        "SD-WAN": [
            _kpi("Worst path packet loss", "sdwan", "loss_pct", "avg", "%", 8, worse([(0.5, "low"), (1, "medium"), (2, "high"), (4, "critical")], "loss_pct", 10)),
            _kpi("Edges reachable", "sdwan", "edges_up", "avg", "edges", 8, better([(0, "critical"), (70, "high"), (74, "medium"), (76, "low"), (77, "normal")], "edges_up", 77)),
            _kpi("Path latency", "sdwan", "path_latency_ms", "avg", "ms", 7, worse([(40, "low"), (60, "medium"), (80, "high"), (120, "critical")], "path_latency_ms")),
        ],
        "PowerMax arrays": [
            _kpi("PowerMax capacity", "powermax", "capacity_pct", "avg", "%", 7, worse([(78, "low"), (85, "medium"), (90, "high"), (95, "critical")], "capacity_pct", 100)),
            _kpi("PowerMax write latency", "powermax", "write_latency_ms", "avg", "ms", 8, worse([(2, "low"), (4, "medium"), (8, "high"), (15, "critical")], "write_latency_ms", 30)),
            _kpi("Days to 80 percent", "powermax", "days_to_80", "avg", "days", 5, better([(0, "critical"), (14, "high"), (30, "medium"), (60, "low"), (90, "normal")], "days_to_80", 180)),
            _kpi("Arrays online", "powermax", "arrays_online", "avg", "arrays", 9, better([(0, "critical"), (1, "high"), (2, "medium"), (3, "low"), (4, "normal")], "arrays_online", 4)),
            _kpi("Allocated capacity", "powermax", "allocated_pb", "avg", "PB", 4, worse([(3.5, "low"), (3.8, "medium"), (4.0, "high"), (4.2, "critical")], "allocated_pb", 5)),
            _kpi("Remaining capacity", "powermax", "remaining_pb", "avg", "PB", 5, better([(0, "critical"), (0.4, "high"), (0.8, "medium"), (1.0, "low"), (1.5, "normal")], "remaining_pb", 3)),
        ],
        "Microsoft Teams": [
            _kpi("Teams successful calls", "teams", "success", "avg", "%", 8, better([(0, "critical"), (80, "high"), (90, "medium"), (96, "low"), (99, "normal")], "success", 100)),
            _kpi("Teams round trip", "teams", "rtt_ms", "avg", "ms", 6, worse([(30, "low"), (40, "medium"), (60, "high"), (80, "critical")], "rtt_ms")),
            _kpi("Teams packet loss", "teams", "packet_loss", "avg", "%", 7, worse([(0.5, "low"), (1, "medium"), (2, "high"), (4, "critical")], "packet_loss", 10)),
        ],
        "Office 365": [
            _kpi("Active incidents", "o365", "incidents", "avg", "incidents", 7, worse([(1, "low"), (2, "medium"), (4, "high"), (8, "critical")], "incidents", 12)),
            _kpi("Service advisories", "o365", "advisories", "avg", "advisories", 4, worse([(1, "low"), (2, "medium"), (4, "high"), (6, "critical")], "advisories")),
        ],
        "Cisco Webex": [
            _kpi("Webex join success", "webex", "join_success", "avg", "%", 7, better([(0, "critical"), (80, "high"), (90, "medium"), (96, "low"), (99, "normal")], "join_success", 100)),
            _kpi("Webex round trip", "webex", "rtt_ms", "avg", "ms", 5, worse([(30, "low"), (45, "medium"), (60, "high"), (80, "critical")], "rtt_ms")),
            _kpi("Webex packet loss", "webex", "packet_loss", "avg", "%", 6, worse([(0.5, "low"), (1, "medium"), (2, "high"), (4, "critical")], "packet_loss", 10)),
        ],
        "AI Agent Observability": [
            _kpi("Hallucination rate", "ai_agent", "hallucination_pct", "avg", "%", 9, worse([(3, "low"), (6, "medium"), (10, "high"), (15, "critical")], "hallucination_pct")),
            _kpi("Prompt injection detections", "ai_agent", "injection_detections", "avg", "detections", 10, worse([(2, "low"), (5, "medium"), (10, "high"), (20, "critical")], "injection_detections")),
            _kpi("Grounded answers", "ai_agent", "grounded_pct", "avg", "%", 8, better([(0, "critical"), (80, "high"), (90, "medium"), (95, "low"), (98, "normal")], "grounded_pct", 100)),
            _kpi("Unsafe output rate", "ai_agent", "unsafe_pct", "avg", "%", 9, worse([(1, "low"), (2.5, "medium"), (5, "high"), (8, "critical")], "unsafe_pct")),
            _kpi("Agent response time", "ai_agent", "response_ms", "avg", "ms", 6, worse([(2000, "low"), (4000, "medium"), (7000, "high"), (12000, "critical")], "response_ms")),
            _kpi("Policy blocks", "ai_agent", "policy_blocks", "avg", "blocks", 7, worse([(5, "low"), (10, "medium"), (20, "high"), (40, "critical")], "policy_blocks")),
        ],
    }
    data.update(leaf_kpis())
    return data


def attach_to_service(title: str, new_kpis: list[dict]):
    found = client.find_by_title("service", title)
    if not found:
        print(f"skip KPIs; service not found: {title}")
        return
    svc = client.get_service(found["_key"])
    existing = list(svc.get("kpis") or [])
    have = {k.get("title") for k in existing}
    added = [k for k in new_kpis if k.get("title") not in have]
    if not added:
        print(f"KPIs on {title}: already present {[k['title'] for k in new_kpis]}")
        return
    client.request(
        "POST",
        f"/servicesNS/nobody/SA-ITOA/itoa_interface/service/{found['_key']}",
        json_body={"kpis": existing + added},
        query={"is_partial_data": "1"},
    )
    print(f"KPIs on {title}: added {[k['title'] for k in added]}")


def apply():
    for title, kpis in catalog().items():
        attach_to_service(title, kpis)
