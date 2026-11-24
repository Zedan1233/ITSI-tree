"""Shared 24h baseline + last-3h degradation sample events."""
from __future__ import annotations

import json
import os
import random
import uuid
from datetime import datetime, timedelta, timezone

from . import client

INDEX = os.environ.get("TAMM_SAMPLE_INDEX", "tamm_feedback")
SOURCETYPE = os.environ.get("TAMM_SAMPLE_SOURCETYPE", "tamm:feedback")
JOURNEY = "apply_for_credit_card"


def degraded(ts: datetime, now: datetime) -> bool:
    return ts >= now - timedelta(hours=3)


def clamp(val, lo, hi):
    return max(lo, min(hi, val))


def gen_feedback(now: datetime) -> list[dict]:
    rng = random.Random(42)
    events = []
    start = now - timedelta(hours=24)
    ts = start
    while ts <= now:
        bad = degraded(ts, now)
        gap = rng.randint(40, 80) if bad else rng.randint(70, 140)
        abandoned = rng.random() < (0.22 if bad else 0.04)
        handle = 0 if abandoned else int(rng.gauss(720 if bad else 280, 80 if bad else 50))
        events.append(
            {
                "time": ts,
                "journey": JOURNEY,
                "channel": "call_center",
                "event_type": "call",
                "call_id": str(uuid.uuid4()),
                "handle_time_sec": max(0, handle),
                "abandoned": 100 if abandoned else 0,
                "repeat_contact": 100 if (not abandoned and rng.random() < (0.28 if bad else 0.08)) else 0,
                "escalated": 100 if (not abandoned and rng.random() < (0.12 if bad else 0.02)) else 0,
                "wait_time_sec": max(5, int(rng.gauss(240 if bad else 45, 30))),
            }
        )
        ts += timedelta(seconds=gap)

    ts = start + timedelta(minutes=3)
    while ts <= now:
        bad = degraded(ts, now)
        csat = max(1.0, min(5.0, rng.gauss(2.4 if bad else 4.3, 0.5)))
        events.append(
            {
                "time": ts,
                "journey": JOURNEY,
                "channel": "survey",
                "event_type": "survey",
                "survey_id": str(uuid.uuid4()),
                "csat": round(csat, 2),
                "ces": round(max(1.0, min(7.0, rng.gauss(5.5 if bad else 2.8, 0.7))), 2),
                "nps": max(0, min(10, int(rng.gauss(4 if bad else 8, 1.5)))),
                "thumbs_down": 100 if rng.random() < (0.45 if bad else 0.08) else 0,
            }
        )
        ts += timedelta(seconds=rng.randint(180, 420))

    ts = start + timedelta(minutes=7)
    platforms = ["twitter", "facebook", "instagram", "tiktok"]
    while ts <= now:
        bad = degraded(ts, now)
        negative = rng.random() < (0.62 if bad else 0.18)
        events.append(
            {
                "time": ts,
                "journey": JOURNEY,
                "channel": "social_media",
                "event_type": "mention",
                "post_id": str(uuid.uuid4()),
                "platform": rng.choice(platforms),
                "negative": 100 if negative else 0,
                "viral": 100 if (negative and rng.random() < (0.18 if bad else 0.03)) else 0,
                "sla_breached": 100 if rng.random() < (0.35 if bad else 0.06) else 0,
                "sentiment_score": round(rng.uniform(-0.9, -0.2) if negative else rng.uniform(0.1, 0.9), 3),
            }
        )
        ts += timedelta(seconds=rng.randint(120, 360))
    return events


def gen_snow_revenue(now: datetime) -> list[dict]:
    rng = random.Random(99)
    events = []
    start = now - timedelta(hours=24)
    ts = start
    ticket = 10000
    while ts <= now:
        bad = degraded(ts, now)
        gap = rng.randint(90, 180) if bad else rng.randint(400, 800)
        major = rng.random() < (0.42 if bad else 0.08)
        resolved = rng.random() < (0.35 if bad else 0.75)
        mtta = max(1, int(rng.gauss(38 if bad else 7, 8)))
        ticket += 1
        events.append(
            {
                "time": ts,
                "journey": JOURNEY,
                "channel": "snow",
                "event_type": "incident",
                "number": f"INC{ticket:07d}",
                "priority": rng.choice([1, 2]) if major else rng.choice([3, 4]),
                "is_p1p2": 100 if major else 0,
                "resolved": 100 if resolved else 0,
                "aged": 100 if ((not resolved) and rng.random() < (0.30 if bad else 0.05)) else 0,
                "mtta_min": mtta,
                "mttr_min": 0 if not resolved else max(mtta + 5, int(rng.gauss(170 if bad else 35, 20))),
                "assignment_group": "QNB-CreditCard",
            }
        )
        ts += timedelta(seconds=gap)

    ts = start + timedelta(minutes=11)
    chg = 2000
    while ts <= now:
        bad = degraded(ts, now)
        chg += 1
        events.append(
            {
                "time": ts,
                "journey": JOURNEY,
                "channel": "snow",
                "event_type": "change",
                "number": f"CHG{chg:07d}",
                "change_failed": 100 if rng.random() < (0.32 if bad else 0.05) else 0,
                "is_p1p2": 0,
                "aged": 0,
                "mtta_min": 0,
                "mttr_min": 0,
            }
        )
        ts += timedelta(seconds=rng.randint(300, 600) if bad else rng.randint(900, 1800))

    ts = start + timedelta(seconds=20)
    while ts <= now:
        bad = degraded(ts, now)
        abandoned = rng.random() < (0.18 if bad else 0.04)
        failed = (not abandoned) and rng.random() < (0.16 if bad else 0.02)
        success = not abandoned and not failed
        events.append(
            {
                "time": ts,
                "journey": JOURNEY,
                "channel": "revenue",
                "event_type": "payment",
                "payment_id": str(uuid.uuid4()),
                "amount_aed": round(max(50.0, rng.gauss(280, 90)), 2),
                "success": 100 if success else 0,
                "failed": 100 if failed else 0,
                "abandoned": 100 if abandoned else 0,
                "refund": 100 if success and rng.random() < (0.09 if bad else 0.012) else 0,
                "method": rng.choice(["card", "apple_pay", "bank_transfer"]),
            }
        )
        ts += timedelta(seconds=rng.randint(20, 45) if bad else rng.randint(40, 90))
    return events


def gen_platform(now: datetime) -> list[dict]:
    rng = random.Random(11)
    events = []
    start = now - timedelta(hours=24)

    def walk(channel, journey, builder, gap_ok=(70, 110), gap_bad=(50, 80)):
        ts = start
        while ts <= now:
            bad = degraded(ts, now)
            ev = builder(bad)
            ev.update({"time": ts, "channel": channel, "journey": journey, "event_type": "snapshot"})
            events.append(ev)
            lo, hi = gap_bad if bad else gap_ok
            ts += timedelta(seconds=rng.randint(lo, hi))

    walk(
        "auth_provider",
        "qnb_platform",
        lambda bad: {
            "success": 100 if rng.random() > (0.28 if bad else 0.012) else 0,
            "latency_ms": int(clamp(rng.gauss(2400 if bad else 380, 180 if bad else 60), 80, 8000)),
            "saml_error": 100 if rng.random() < (0.14 if bad else 0.008) else 0,
            "mfa_fail": 100 if rng.random() < (0.11 if bad else 0.015) else 0,
        },
    )
    walk(
        "authentication",
        "qnb_platform",
        lambda bad: {"session_ok": 100 if rng.random() > (0.26 if bad else 0.01) else 0},
    )
    walk(
        "appdynamics",
        "qnb_platform",
        lambda bad: {
            "ingest_healthy": clamp(rng.gauss(72 if bad else 99.4, 4), 0, 100),
            "bt_error_rate": clamp(rng.gauss(7.5 if bad else 0.35, 1.2 if bad else 0.15), 0, 40),
            "open_problems": max(0, int(rng.gauss(11 if bad else 1, 2))),
            "dropped_agents": max(0, int(rng.gauss(5 if bad else 0.1, 1.5))),
        },
    )
    walk(
        "azure",
        "qnb_platform",
        lambda bad: {
            "unhealthy_resources": max(0, int(rng.gauss(7 if bad else 0.2, 1.5))),
            "appservice_avail": clamp(rng.gauss(91 if bad else 99.7, 1.5), 70, 100),
            "pipeline_fail": 100 if rng.random() < (0.22 if bad else 0.02) else 0,
            "ingest_delay_sec": max(1, int(rng.gauss(160 if bad else 8, 25 if bad else 3))),
        },
    )
    walk(
        "kubernetes",
        "qnb_platform",
        lambda bad: {
            "crashloop_pct": clamp(rng.gauss(16 if bad else 0.8, 3 if bad else 0.3), 0, 50),
            "node_notready": max(0, int(rng.gauss(2 if bad else 0, 0.6))),
            "ingress_5xx": clamp(rng.gauss(8.5 if bad else 0.25, 1.5 if bad else 0.1), 0, 40),
            "pending_pods": max(0, int(rng.gauss(12 if bad else 0.3, 3))),
        },
    )
    walk(
        "database",
        JOURNEY,
        lambda bad: {
            "query_p95_ms": max(10, int(rng.gauss(1600 if bad else 85, 200 if bad else 15))),
            "lock_wait_ms": max(0, int(rng.gauss(380 if bad else 12, 60 if bad else 5))),
            "conn_error_rate": clamp(rng.gauss(12 if bad else 0.4, 2 if bad else 0.15), 0, 40),
            "conn_sat_pct": clamp(rng.gauss(91 if bad else 44, 3), 10, 100),
            "repl_lag_sec": max(0, int(rng.gauss(42 if bad else 1.2, 8 if bad else 0.4))),
            "storage_pct": clamp(rng.gauss(79 if bad else 71, 1.2), 40, 95),
        },
    )
    walk(
        "ad_connect",
        JOURNEY,
        lambda bad: {
            "availability": clamp(rng.gauss(84 if bad else 99.6, 2), 60, 100),
            "handshake_fail": clamp(rng.gauss(20 if bad else 0.8, 3 if bad else 0.2), 0, 50),
            "consumer_error": clamp(rng.gauss(17 if bad else 1.5, 3 if bad else 0.3), 0, 50),
            "cert_days_left": 11,
        },
    )
    return events


LEAF_PROFILES = {
    "apm": [
        ("error_pct", 0.4, 4.8, 0.08, "pct"),
        ("response_ms", 160, 1100, 20, "int"),
        ("throughput", 140, 55, 3, "int"),
    ],
    "rum": [
        ("visitors", 2400, 900, 30, "int"),
        ("page_load_ms", 850, 3200, 40, "int"),
        ("client_error_pct", 0.3, 5.5, 0.1, "pct"),
    ],
    "snow": [
        ("p1p2_pct", 5, 26, 0.4, "pct"),
        ("mttr_min", 32, 125, 3, "int"),
        ("aged_pct", 3, 18, 0.4, "pct"),
    ],
    "calls": [
        ("calls", 3, 12, 0.4, "int"),
        ("abandon_pct", 2, 16, 0.3, "pct"),
        ("handle_sec", 260, 640, 8, "int"),
    ],
    "survey": [
        ("csat", 4.4, 2.6, 0.05, "score"),
        ("responses", 8, 28, 1, "int"),
        ("thumbs_down_pct", 5, 32, 0.5, "pct"),
    ],
    "social": [
        ("posts", 2, 11, 0.3, "int"),
        ("negative_pct", 12, 48, 1, "pct"),
        ("sla_pct", 3, 30, 0.4, "pct"),
    ],
    "revenue": [
        ("success_pct", 98, 84, 0.3, "pct"),
        ("failed_pct", 1.2, 13, 0.2, "pct"),
        ("incomplete", 0.4, 5.5, 0.2, "num"),
    ],
    "judicial": [
        ("completion_pct", 97, 86, 0.3, "pct"),
        ("delay_min", 12, 55, 1, "int"),
        ("open_cases", 18, 64, 1, "int"),
    ],
    "health": [
        ("success_pct", 98, 88, 0.3, "pct"),
        ("lookup_ms", 220, 1400, 15, "int"),
        ("open_referrals", 6, 22, 0.6, "int"),
    ],
    "eligibility": [
        ("approval_pct", 98, 78, 0.3, "pct"),
        ("decision_ms", 220, 1600, 20, "int"),
        ("error_pct", 0.4, 6.5, 0.1, "pct"),
    ],
    "printing": [
        ("success_pct", 99, 86, 0.2, "pct"),
        ("fulfill_min", 18, 150, 4, "int"),
        ("reprint_pct", 0.8, 9.5, 0.2, "pct"),
    ],
}


def _profile_value(rng, bad, spec):
    name, ok, deg, spread, how = spec
    val = rng.gauss(deg if bad else ok, spread)
    if how == "int":
        return name, max(0, int(round(val)))
    if how == "pct":
        return name, round(clamp(val, 0, 100), 2)
    if how == "score":
        return name, round(clamp(val, 1, 5), 2)
    return name, round(max(0.0, val), 2)


def gen_leaf_services(now: datetime) -> list[dict]:
    """One snapshot every three minutes for leaf services that had no KPI data."""
    from .kpis import LEAF_SERVICES

    rng = random.Random(21)
    events = []
    start = now - timedelta(hours=24)
    for title, channel, kind in LEAF_SERVICES:
        ts = start
        while ts <= now:
            fields = dict(_profile_value(rng, degraded(ts, now), spec) for spec in LEAF_PROFILES[kind])
            events.append(
                {
                    "time": ts,
                    "journey": "qnb_service",
                    "channel": channel,
                    "service": title,
                    "event_type": "snapshot",
                    **fields,
                }
            )
            ts += timedelta(seconds=180)
    return events


def generate_ai_agent(start: datetime, end: datetime) -> list[dict]:
    """Agent-quality snapshots. Recent values sit in a mixed, mostly healthy band."""
    rng = random.Random(21)
    events = []
    ts = start
    while ts <= end:
        events.append(
            {
                "time": ts,
                "journey": "qnb_demo",
                "channel": "ai_agent",
                "service": "AI Agent Observability",
                "event_type": "snapshot",
                "hallucination_pct": round(clamp(rng.gauss(4.5, 0.15), 0, 100), 2),
                "injection_detections": max(0, int(round(rng.gauss(6.4, 0.35)))),
                "grounded_pct": round(clamp(rng.gauss(96.2, 0.15), 0, 100), 2),
                "unsafe_pct": round(clamp(rng.gauss(0.4, 0.05), 0, 100), 2),
                "response_ms": max(0, int(round(rng.gauss(900, 30)))),
                "policy_blocks": max(0, int(round(rng.gauss(2.2, 0.4)))),
            }
        )
        ts += timedelta(seconds=120)
    return events


def generate_hallucination_spike(start: datetime, end: datetime) -> list[dict]:
    """Dense snapshots that hold hallucination rate in the high band (10–15%)."""
    rng = random.Random(22)
    events = []
    ts = start
    while ts <= end:
        events.append(
            {
                "time": ts,
                "journey": "qnb_demo",
                "channel": "ai_agent",
                "service": "AI Agent Observability",
                "event_type": "snapshot",
                "hallucination_pct": round(clamp(rng.gauss(12.4, 0.2), 11.5, 13.8), 2),
                "injection_detections": max(0, int(round(rng.gauss(6.4, 0.35)))),
                "grounded_pct": round(clamp(rng.gauss(96.2, 0.15), 0, 100), 2),
                "unsafe_pct": round(clamp(rng.gauss(0.4, 0.05), 0, 100), 2),
                "response_ms": max(0, int(round(rng.gauss(900, 30)))),
                "policy_blocks": max(0, int(round(rng.gauss(2.2, 0.4)))),
            }
        )
        ts += timedelta(seconds=20)
    return events


def generate_qnb_environment(start: datetime, end: datetime) -> list[dict]:
    """QNB environment snapshots. APM and CPU sit in low; the rest stay healthy."""
    rng = random.Random(24)
    events = []
    ts = start
    while ts <= end:
        events.append(
            {
                "time": ts,
                "journey": "qnb_environment",
                "channel": "adp_env_apm",
                "service": "APM (QNB environment)",
                "event_type": "snapshot",
                "error_pct": round(clamp(rng.gauss(1.35, 0.08), 1.05, 1.85), 2),
                "response_ms": int(round(clamp(rng.gauss(320, 12), 250, 390))),
                "throughput": int(round(clamp(rng.gauss(155, 4), 135, 180))),
            }
        )
        events.append(
            {
                "time": ts,
                "journey": "qnb_environment",
                "channel": "adp_env_infra",
                "service": "Infrastructure (QNB environment)",
                "event_type": "snapshot",
                "availability": round(clamp(rng.gauss(99.8, 0.04), 99.55, 100), 2),
                "cpu_pct": round(clamp(rng.gauss(62, 1.0), 56, 68), 2),
                "disk_ms": round(clamp(rng.gauss(8, 0.5), 2, 14), 2),
            }
        )
        events.append(
            {
                "time": ts,
                "journey": "qnb_environment",
                "channel": "adp_env_network",
                "service": "Network (QNB environment)",
                "event_type": "snapshot",
                "availability": round(clamp(rng.gauss(99.75, 0.04), 99.55, 100), 2),
                "rtt_ms": int(round(clamp(rng.gauss(12, 1), 4, 18))),
                "interface_errors": max(0, int(round(rng.gauss(1.1, 0.3)))),
            }
        )
        ts += timedelta(seconds=60)
    return events


def generate(now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    return (
        gen_feedback(now)
        + gen_snow_revenue(now)
        + gen_platform(now)
        + generate_source_dashboards(now)
        + gen_leaf_services(now)
        + generate_ai_agent(now - timedelta(hours=24), now)
        + generate_qnb_environment(now - timedelta(hours=24), now)
    )


def ensure_index():
    try:
        client.request("GET", f"/services/data/indexes/{INDEX}", query={"output_mode": "json"})
        print(f"index {INDEX} exists")
        return
    except RuntimeError as exc:
        if "404" not in str(exc) and "409" not in str(exc):
            print(f"index lookup: {exc}")
    try:
        client.request(
            "POST",
            "/services/data/indexes",
            form={"name": INDEX, "datatype": "event"},
            query={"output_mode": "json"},
        )
        print(f"created index {INDEX}")
    except RuntimeError as exc:
        if "409" in str(exc) or "already exists" in str(exc).lower():
            print(f"index {INDEX} already exists")
            return
        raise


def ingest(events: list[dict], host: str = "qnb-lab") -> int:
    sent = 0
    batch = []

    def flush():
        nonlocal sent, batch
        if not batch:
            return
        client.request(
            "POST",
            "/services/receivers/simple",
            query={"index": INDEX, "source": "qnb_lab", "sourcetype": SOURCETYPE, "host": host},
            raw="\n".join(batch) + "\n",
        )
        sent += len(batch)
        batch = []

    for ev in events:
        ts = ev.pop("time")
        batch.append(ts.strftime("%Y-%m-%d %H:%M:%S ") + json.dumps(ev, separators=(",", ":")))
        if len(batch) >= 80:
            flush()
            print(f"ingested {sent} events", flush=True)
    flush()
    return sent


def generate_source_dashboards(now: datetime | None = None) -> list[dict]:
    """Sample telemetry for the business and infrastructure source dashboards."""
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    rng = random.Random(7)
    events = []
    ts = now - timedelta(hours=24)
    while ts <= now:
        bad = degraded(ts, now)

        def add(channel, **fields):
            events.append(
                {
                    "time": ts,
                    "journey": "qnb_platform",
                    "channel": channel,
                    "event_type": channel,
                    **fields,
                }
            )

        add(
            "switch",
            availability=round(rng.gauss(96.2 if bad else 99.93, 0.05), 2),
            port_use=round(rng.gauss(78 if bad else 63, 0.4), 1),
            interface_errors=14 if bad else 2,
        )
        add(
            "netflow",
            gbps=round(max(0.1, rng.gauss(9.0 if bad else 18.4, 0.3)), 2),
            flows_per_min=int(rng.gauss(4500000 if bad else 3800000, 20000)),
            anomalies=7 if bad else 1,
        )
        add(
            "packet",
            gbps=round(max(0.1, rng.gauss(2.2 if bad else 4.6, 0.1)), 2),
            protocols=31,
            degradations=2 if bad else 0,
        )
        add(
            "firewall",
            health_pct=round(rng.gauss(89 if bad else 98.4, 0.3), 2),
            nodes_online=18,
            connection_pct=round(rng.gauss(68 if bad else 45, 0.4), 1),
            health_alerts=1 if bad else 0,
        )
        add(
            "sdwan",
            loss_pct=round(max(0, rng.gauss(1.8 if bad else 0.2, 0.04)), 2),
            edges_up=76 if bad else 77,
            path_latency_ms=round(rng.gauss(68 if bad else 30, 0.5), 1),
        )
        add(
            "powermax",
            capacity_pct=72,
            write_latency_ms=round(max(0.2, rng.gauss(5.2 if bad else 1.1, 0.08)), 2),
            days_to_80=40 if bad else 92,
            arrays_online=4,
            allocated_pb=3.1,
            remaining_pb=1.2,
        )
        add(
            "teams",
            success=round(rng.gauss(98.6 if bad else 99.5, 0.04), 2),
            rtt_ms=round(rng.gauss(46 if bad else 28, 0.4), 1),
            packet_loss=round(max(0, rng.gauss(1.2 if bad else 0.3, 0.02)), 2),
        )
        add("o365", incidents=0, advisories=2 if bad else 0)
        add(
            "webex",
            join_success=round(rng.gauss(99.2 if bad else 99.6, 0.03), 2),
            rtt_ms=round(rng.gauss(38 if bad else 24, 0.3), 1),
            packet_loss=round(max(0, rng.gauss(0.4 if bad else 0.2, 0.02)), 2),
        )
        add("infra_alert", critical=1 if bad else 0)
        for n in range(4 if bad else 8):
            add("app_visitors", visitor_id=f"visitor-{n}")
        ts += timedelta(minutes=3)
    return events


def apply_source_samples():
    ensure_index()
    events = generate_source_dashboards()
    counts: dict[str, int] = {}
    for ev in events:
        counts[ev["channel"]] = counts.get(ev["channel"], 0) + 1
    sent = ingest([dict(ev) for ev in events])
    print(json.dumps({"sent": sent, "by_channel": counts}, indent=2))
    return sent


def apply():
    ensure_index()
    events = generate()
    counts: dict[str, int] = {}
    for ev in events:
        counts[ev["channel"]] = counts.get(ev["channel"], 0) + 1
    sent = ingest([dict(ev) for ev in events])
    print(json.dumps({"sent": sent, "by_channel": counts}, indent=2))
    return sent
