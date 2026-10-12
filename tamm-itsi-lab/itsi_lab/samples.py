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
JOURNEY = "pay_traffic_fines"


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
                "assignment_group": "TAMM-PayFines",
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
                "method": rng.choice(["uae_pass_wallet", "card", "apple_pay"]),
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
        "uaepass",
        "tamm_platform",
        lambda bad: {
            "success": 100 if rng.random() > (0.28 if bad else 0.012) else 0,
            "latency_ms": int(clamp(rng.gauss(2400 if bad else 380, 180 if bad else 60), 80, 8000)),
            "saml_error": 100 if rng.random() < (0.14 if bad else 0.008) else 0,
            "mfa_fail": 100 if rng.random() < (0.11 if bad else 0.015) else 0,
        },
    )
    walk(
        "authentication",
        "tamm_platform",
        lambda bad: {"session_ok": 100 if rng.random() > (0.26 if bad else 0.01) else 0},
    )
    walk(
        "appdynamics",
        "tamm_platform",
        lambda bad: {
            "ingest_healthy": clamp(rng.gauss(72 if bad else 99.4, 4), 0, 100),
            "bt_error_rate": clamp(rng.gauss(7.5 if bad else 0.35, 1.2 if bad else 0.15), 0, 40),
            "open_problems": max(0, int(rng.gauss(11 if bad else 1, 2))),
            "dropped_agents": max(0, int(rng.gauss(5 if bad else 0.1, 1.5))),
        },
    )
    walk(
        "azure",
        "tamm_platform",
        lambda bad: {
            "unhealthy_resources": max(0, int(rng.gauss(7 if bad else 0.2, 1.5))),
            "appservice_avail": clamp(rng.gauss(91 if bad else 99.7, 1.5), 70, 100),
            "pipeline_fail": 100 if rng.random() < (0.22 if bad else 0.02) else 0,
            "ingest_delay_sec": max(1, int(rng.gauss(160 if bad else 8, 25 if bad else 3))),
        },
    )
    walk(
        "kubernetes",
        "tamm_platform",
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


def generate(now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    return gen_feedback(now) + gen_snow_revenue(now) + gen_platform(now)


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


def ingest(events: list[dict], host: str = "tamm-lab") -> int:
    sent = 0
    batch = []

    def flush():
        nonlocal sent, batch
        if not batch:
            return
        client.request(
            "POST",
            "/services/receivers/simple",
            query={"index": INDEX, "source": "tamm_lab", "sourcetype": SOURCETYPE, "host": host},
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


def apply():
    ensure_index()
    events = generate()
    counts: dict[str, int] = {}
    for ev in events:
        counts[ev["channel"]] = counts.get(ev["channel"], 0) + 1
    sent = ingest([dict(ev) for ev in events])
    print(json.dumps({"sent": sent, "by_channel": counts}, indent=2))
    return sent
