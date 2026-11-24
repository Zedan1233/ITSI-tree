"""Mixed KPI data and one episode per leaf, covering the next few hours."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

from . import client
from .episodes import break_open_lab_episodes, enable_service_policy, post_notable
from .kpis import catalog
from .samples import ensure_index, ingest
from .tree import load_tree

# Aimed mix across the 28 leaves: mostly healthy, with visible low/medium/high/critical.
PATTERN = [
    "normal",
    "low",
    "medium",
    "normal",
    "high",
    "normal",
    "critical",
    "medium",
    "low",
    "normal",
]
WORSE_RANK = {"normal": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
HEALTHIER = {"critical": "high", "high": "medium", "medium": "low", "low": "normal", "normal": "normal"}
ITSI_SEVERITY = {"critical": "6", "high": "5", "medium": "4", "low": "3", "normal": "3"}
STATUS_CYCLE = ["1", "2", "3"]  # New, In Progress, Pending
LABEL = {"critical": "Critical", "high": "High", "medium": "Medium", "low": "Low", "normal": "Normal"}


def leaf_titles() -> list[str]:
    def walk(node):
        children = node.get("children") or []
        if not children:
            yield node["title"]
            return
        for child in children:
            yield from walk(child)

    return list(walk(load_tree()["root"]))


def channel_of(kpi: dict) -> str:
    match = re.search(r'channel="([^"]+)"', kpi["base_search"])
    if not match:
        raise ValueError(f"KPI {kpi['title']} has no channel")
    return match.group(1)


def severity_of(kpi: dict, value: float) -> str:
    levels = kpi["aggregate_thresholds"]["thresholdLevels"]
    matched = kpi["aggregate_thresholds"]["baseSeverityLabel"]
    for level in sorted(levels, key=lambda item: float(item["thresholdValue"])):
        if value + 1e-9 >= float(level["thresholdValue"]):
            matched = level["severityLabel"]
    return matched


def _integer_metric(kpi: dict) -> bool:
    if kpi["aggregate_statop"] in ("count", "dc"):
        return True
    values = [float(level["thresholdValue"]) for level in kpi["aggregate_thresholds"]["thresholdLevels"]]
    return all(value.is_integer() for value in values)


def band_value(kpi: dict, severity: str) -> float:
    """A value that lands in `severity` for this KPI's static thresholds."""
    levels = sorted(
        kpi["aggregate_thresholds"]["thresholdLevels"],
        key=lambda item: float(item["thresholdValue"]),
    )
    base = kpi["aggregate_thresholds"]["baseSeverityLabel"]
    if severity == "normal" and base == "normal":
        raw = float(levels[0]["thresholdValue"]) * 0.35
    elif severity == "critical" and base == "critical":
        nxt = [level for level in levels if level["severityLabel"] != "critical"]
        raw = float(nxt[0]["thresholdValue"]) * 0.45 if nxt else 0.0
    else:
        wanted = severity
        if wanted not in {level["severityLabel"] for level in levels}:
            wanted = "normal" if base == "critical" else "low"
        lo = float(next(level["thresholdValue"] for level in levels if level["severityLabel"] == wanted))
        higher = [level for level in levels if float(level["thresholdValue"]) > lo]
        if not higher:
            raw = lo if base == "critical" else lo + max(lo * 0.2, 1.0 if lo >= 1 else 0.2)
        else:
            hi = float(higher[0]["thresholdValue"])
            raw = lo + (hi - lo) * 0.45
    value = max(0.0, raw)
    if _integer_metric(kpi):
        candidate = int(round(value))
        if severity_of(kpi, candidate) != severity:
            for step in range(0, 30):
                for guess in (candidate - step, candidate + step):
                    if guess >= 0 and severity_of(kpi, guess) == severity:
                        return float(guess)
        return float(max(0, candidate))
    return round(value, 4)


def _unique_kpis(kpis: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for kpi in kpis:
        if kpi["threshold_field"] in seen:
            continue
        seen.add(kpi["threshold_field"])
        unique.append(kpi)
    return unique


def _eligible(kpis: list[dict]) -> list[dict]:
    """Skip count KPIs that only match a 0/100 filter; those cannot be colored on their own."""
    chosen = []
    for kpi in _unique_kpis(kpis):
        search = kpi["base_search"]
        if kpi["aggregate_statop"] == "count" and ("=100" in search or "!=100" in search):
            continue
        chosen.append(kpi)
    return chosen or _unique_kpis(kpis)


def make_plan(title: str, kpis: list[dict], headline: str, index: int) -> dict:
    eligible = _eligible(kpis)
    focus = eligible[index % len(eligible)]
    secondary = eligible[(eligible.index(focus) + 1) % len(eligible)]
    severities = {}
    for kpi in _unique_kpis(kpis):
        if kpi["threshold_field"] == focus["threshold_field"]:
            severities[kpi["title"]] = headline
        elif headline != "normal" and kpi["threshold_field"] == secondary["threshold_field"]:
            severities[kpi["title"]] = HEALTHIER[headline]
        else:
            severities[kpi["title"]] = "normal"
    # Duplicate titles that share a field (Query P95 / Response time) follow that field.
    by_field = {kpi["threshold_field"]: severities[kpi["title"]] for kpi in _unique_kpis(kpis) if kpi["title"] in severities}
    for kpi in kpis:
        severities[kpi["title"]] = by_field.get(kpi["threshold_field"], "normal")
    return {
        "title": title,
        "index": index,
        "headline": headline,
        "channel": channel_of(kpis[0]),
        "kpis": kpis,
        "severities": severities,
        "status": STATUS_CYCLE[index % len(STATUS_CYCLE)],
    }


def assign_plans() -> list[dict]:
    titles = leaf_titles()
    cat = catalog()
    plans = []
    for index, title in enumerate(titles):
        plans.append(make_plan(title, cat[title], PATTERN[index % len(PATTERN)], index))
    by_channel: dict[str, list[dict]] = {}
    for plan in plans:
        by_channel.setdefault(plan["channel"], []).append(plan)
    synced = []
    for plan in plans:
        group = by_channel[plan["channel"]]
        if len(group) == 1:
            synced.append(plan)
            continue
        worst = max(group, key=lambda item: WORSE_RANK[item["headline"]])
        synced.append(make_plan(plan["title"], plan["kpis"], worst["headline"], plan["index"]))
    return synced


def _worse(left: str, right: str) -> str:
    return left if WORSE_RANK[left] >= WORSE_RANK[right] else right


def _kpis_for_channel(channel: str) -> list[dict]:
    found = []
    for kpis in catalog().values():
        for kpi in kpis:
            if channel_of(kpi) == channel:
                found.append(kpi)
    return found


def _fit_flag(count_kpi, count_severity, flag_kpi, flag_severity, floor: int) -> tuple[int, int]:
    def matches(count: int, flagged: int) -> bool:
        rate = 0 if count == 0 else 100.0 * flagged / count
        return severity_of(flag_kpi, rate) == flag_severity and (
            count_kpi is None or severity_of(count_kpi, count) == count_severity
        )

    for count in range(max(1, floor), max(1, floor) + 40):
        for flagged in range(count + 1):
            if matches(count, flagged):
                return count, flagged
    for count in range(1, 40):
        for flagged in range(count + 1):
            rate = 100.0 * flagged / count
            if severity_of(flag_kpi, rate) == flag_severity:
                return count, flagged
    return max(1, floor), 0


def compile_channels(plans: list[dict]) -> dict[str, dict]:
    """Per-channel event recipe and the KPI value that recipe produces in a 5-minute window."""
    field_severity: dict[tuple[str, str], str] = {}
    kpi_for_field: dict[tuple[str, str], dict] = {}
    for plan in plans:
        for kpi in plan["kpis"]:
            key = (channel_of(kpi), kpi["threshold_field"])
            severity = plan["severities"][kpi["title"]]
            if key not in field_severity or WORSE_RANK[severity] > WORSE_RANK[field_severity[key]]:
                field_severity[key] = severity
                kpi_for_field[key] = kpi
    # Parent KPIs on channels no leaf writes, held at normal so those scores stay current.
    for kpis in catalog().values():
        for kpi in kpis:
            key = (channel_of(kpi), kpi["threshold_field"])
            if key not in field_severity:
                field_severity[key] = "normal"
                kpi_for_field[key] = kpi

    # A success rate and a failure rate on the same events have to move together.
    coupled = {
        "success": ("failed", "abandoned", "saml_error", "mfa_fail"),
        "success_pct": ("failed_pct",),
    }
    for channel in {key[0] for key in field_severity}:
        for good, bads in coupled.items():
            if (channel, good) not in field_severity:
                continue
            severity = field_severity[(channel, good)]
            for bad in bads:
                if (channel, bad) in field_severity:
                    severity = _worse(severity, field_severity[(channel, bad)])
            field_severity[(channel, good)] = severity

    channels = sorted({key[0] for key in field_severity})
    specs = {}
    for channel in channels:
        kpis = _kpis_for_channel(channel)
        by_field: dict[str, dict] = {}
        for kpi in kpis:
            by_field.setdefault(kpi["threshold_field"], kpi)
        severity_by_field = {field: field_severity[(channel, field)] for field in by_field}
        spec = _compile_one(channel, by_field, severity_by_field, kpis)
        specs[channel] = spec
    return specs


def _compile_one(channel: str, by_field: dict[str, dict], severity_by_field: dict[str, str], kpis: list[dict]) -> dict:
    values = {field: band_value(kpi, severity_by_field[field]) for field, kpi in by_field.items()}
    searches = {kpi["threshold_field"]: kpi["base_search"] for kpi in kpis}

    if channel == "snow":
        return {
            "kind": "snow",
            "values": values,
            "kpi_values": _snow_kpi_values(kpis, values),
        }
    if channel == "call_center":
        calls = next(kpi for kpi in kpis if kpi["title"] == "Call-center calls")
        abandon = next(kpi for kpi in kpis if kpi["title"] == "Abandonment Rate")
        count, flagged = _fit_flag(
            calls,
            severity_by_field["_time"] if calls["threshold_field"] == "_time" else severity_of(calls, values["_time"]),
            abandon,
            severity_by_field["abandoned"],
            max(1, int(values["_time"])),
        )
        # _time is shared by two count KPIs. The sensitive one (Call-center calls) wins;
        # re-read its severity from `count` in case the flag fit had to move it.
        call_value = float(count)
        rate = 0 if count == 0 else 100.0 * flagged / count
        kpi_values = {}
        for kpi in kpis:
            if kpi["aggregate_statop"] == "count":
                kpi_values[kpi["title"]] = call_value
            elif kpi["threshold_field"] == "abandoned":
                kpi_values[kpi["title"]] = rate
            else:
                kpi_values[kpi["title"]] = values[kpi["threshold_field"]]
        return {
            "kind": "call_center",
            "count": count,
            "abandoned": flagged,
            "values": values,
            "kpi_values": kpi_values,
        }
    if channel == "revenue":
        dc_kpi = next((kpi for kpi in kpis if kpi["aggregate_statop"] == "dc"), None)
        count = max(2, int(values[dc_kpi["threshold_field"]])) if dc_kpi else 2
        success = values.get("success", values.get("success_pct", 100))
        return {
            "kind": "revenue",
            "count": count,
            "success": success,
            "values": values,
            "kpi_values": _revenue_kpi_values(kpis, values, count, success),
        }

    count_kpis = [kpi for kpi in kpis if kpi["aggregate_statop"] == "count" and "=100" not in kpi["base_search"]]
    dc_kpis = [kpi for kpi in kpis if kpi["aggregate_statop"] == "dc"]
    if count_kpis:
        controller = min(
            count_kpis,
            key=lambda kpi: min(
                float(level["thresholdValue"])
                for level in kpi["aggregate_thresholds"]["thresholdLevels"]
                if level["severityLabel"] == "critical"
            ),
        )
        count = max(1, int(values[controller["threshold_field"]]))
    elif dc_kpis:
        count = max(1, int(max(values[kpi["threshold_field"]] for kpi in dc_kpis)))
    else:
        count = 2
    sum_fields = {kpi["threshold_field"] for kpi in kpis if kpi["aggregate_statop"] == "sum"}
    avg_fields = {
        kpi["threshold_field"]
        for kpi in kpis
        if kpi["aggregate_statop"] == "avg" and kpi["threshold_field"] not in sum_fields
    }
    kpi_values = {}
    for kpi in kpis:
        if kpi["aggregate_statop"] in ("count", "dc"):
            kpi_values[kpi["title"]] = float(count)
        else:
            kpi_values[kpi["title"]] = values[kpi["threshold_field"]]
    return {
        "kind": "gauge" if not dc_kpis else "dc",
        "count": count,
        "avg": {field: values[field] for field in avg_fields},
        "sum": {field: values[field] for field in sum_fields},
        "dc": [kpi["threshold_field"] for kpi in dc_kpis],
        "values": values,
        "kpi_values": kpi_values,
        "searches": searches,
    }


def _snow_kpi_values(kpis: list[dict], values: dict) -> dict:
    out = {}
    for kpi in kpis:
        out[kpi["title"]] = values[kpi["threshold_field"]]
    return out


def _revenue_window(count: int, success_target: float, values: dict) -> list[dict]:
    if success_target >= 96:
        successes = [100.0] * count
        amounts = [700.0] * count
    else:
        rest = (success_target * count - 100.0) / (count - 1)
        rest = min(100.0, max(0.0, rest))
        successes = [100.0] + [rest] * (count - 1)
        amounts = [1600.0] + [0.0] * (count - 1)
    events = []
    for index, (success, amount) in enumerate(zip(successes, amounts)):
        events.append(
            {
                "success": round(success, 4),
                "success_pct": round(success, 4),
                "failed": values.get("failed", 0),
                "failed_pct": values.get("failed_pct", values.get("failed", 0)),
                "abandoned": values.get("abandoned", 0),
                "refund": values.get("refund", 0),
                "incomplete": values.get("incomplete", 0),
                "amount_aed": amount,
                "payment_id": f"pay-{index}",
            }
        )
    return events


def _revenue_kpi_values(kpis: list[dict], values: dict, count: int, success_target: float) -> dict:
    sample = _revenue_window(count, success_target, values)
    success_avg = sum(row["success"] for row in sample) / count
    collected = sum(row["amount_aed"] for row in sample if row["success"] >= 100)
    unpaid = sum(row["amount_aed"] for row in sample if row["success"] < 100)
    incomplete = 0
    out = {}
    for kpi in kpis:
        field = kpi["threshold_field"]
        if kpi["aggregate_statop"] == "dc":
            out[kpi["title"]] = float(count)
        elif kpi["aggregate_statop"] == "count":
            out[kpi["title"]] = float(incomplete)
        elif kpi["aggregate_statop"] == "sum" and "success=100" in kpi["base_search"]:
            out[kpi["title"]] = collected
        elif kpi["aggregate_statop"] == "sum":
            out[kpi["title"]] = unpaid
        elif field in ("success", "success_pct"):
            out[kpi["title"]] = success_avg
        else:
            out[kpi["title"]] = float(values.get(field, 0))
    return out


def demo_window(now: datetime, last_event: datetime | None = None) -> tuple[datetime, datetime]:
    start = last_event + timedelta(minutes=2) if last_event else now - timedelta(hours=8)
    end = now + timedelta(hours=3, minutes=10)
    return start, end


def _buckets(start: datetime, end: datetime):
    minute = (start.minute // 5) * 5
    cursor = start.replace(minute=minute, second=0, microsecond=0)
    if cursor < start:
        cursor += timedelta(minutes=5)
    while cursor + timedelta(minutes=4) <= end:
        yield cursor
        cursor += timedelta(minutes=5)


def _stamp(bucket: datetime, index: int, count: int) -> datetime:
    span = 300 / max(count, 1)
    return bucket + timedelta(seconds=min(299, int((index + 0.5) * span)))


def generate_demo(start: datetime, end: datetime, plans: list[dict] | None = None, specs: dict | None = None) -> list[dict]:
    plans = plans or assign_plans()
    specs = specs or compile_channels(plans)
    events = []
    for bucket_index, bucket in enumerate(_buckets(start, end)):
        for channel, spec in specs.items():
            events.extend(_events_for_bucket(channel, spec, bucket, bucket_index))
    return events


def _base_event(bucket_time: datetime, channel: str, bucket_index: int) -> dict:
    return {
        "time": bucket_time,
        "journey": "qnb_demo",
        "channel": channel,
        "event_type": channel,
        "demo_bucket": bucket_index,
    }


def _events_for_bucket(channel: str, spec: dict, bucket: datetime, bucket_index: int) -> list[dict]:
    kind = spec["kind"]
    if kind == "snow":
        return _snow_events(channel, spec, bucket, bucket_index)
    if kind == "call_center":
        return _call_events(channel, spec, bucket, bucket_index)
    if kind == "revenue":
        return _revenue_events(channel, spec, bucket, bucket_index)
    count = spec["count"]
    rows = []
    for index in range(count):
        row = _base_event(_stamp(bucket, index, count), channel, bucket_index)
        for field, value in spec.get("avg", {}).items():
            row[field] = value
        for field, value in spec.get("sum", {}).items():
            row[field] = value if index == 0 else 0
        for field in spec.get("dc", []):
            row[field] = f"{channel}-{bucket_index}-{index}"
        rows.append(row)
    return rows


def _snow_events(channel: str, spec: dict, bucket: datetime, bucket_index: int) -> list[dict]:
    values = spec["values"]
    rows = []
    for index in range(2):
        row = _base_event(_stamp(bucket, index, 4), channel, bucket_index)
        row.update(
            {
                "event_type": "incident",
                "resolved": 100,
                "is_p1p2": values.get("is_p1p2", 0),
                "mtta_min": values.get("mtta_min", 0),
                "mttr_min": values.get("mttr_min", 0),
                "aged": values.get("aged", 0),
                "p1p2_pct": values.get("p1p2_pct", 0),
                "aged_pct": values.get("aged_pct", 0),
            }
        )
        rows.append(row)
    for index in range(2):
        row = _base_event(_stamp(bucket, index + 2, 4), channel, bucket_index)
        row.update({"event_type": "change", "change_failed": values.get("change_failed", 0)})
        rows.append(row)
    return rows


def _call_events(channel: str, spec: dict, bucket: datetime, bucket_index: int) -> list[dict]:
    count = spec["count"]
    rows = []
    for index in range(count):
        row = _base_event(_stamp(bucket, index, count), channel, bucket_index)
        abandoned = 100 if index < spec["abandoned"] else 0
        row.update(
            {
                "event_type": "call",
                "abandoned": abandoned,
                "handle_time_sec": spec["values"].get("handle_time_sec", 0),
                "repeat_contact": spec["values"].get("repeat_contact", 0),
                "escalated": spec["values"].get("escalated", 0),
            }
        )
        rows.append(row)
    return rows


def _revenue_events(channel: str, spec: dict, bucket: datetime, bucket_index: int) -> list[dict]:
    sample = _revenue_window(spec["count"], spec["success"], spec["values"])
    rows = []
    for index, fields in enumerate(sample):
        row = _base_event(_stamp(bucket, index, spec["count"]), channel, bucket_index)
        row.update(fields)
        row["event_type"] = "payment"
        row["payment_id"] = f"pay-{bucket_index}-{index}"
        rows.append(row)
    return rows


def _fmt(value: float) -> str:
    if abs(value - round(value)) < 1e-6 and abs(value) >= 1:
        return str(int(round(value)))
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text or "0"


def actual_severities(plans: list[dict], specs: dict) -> dict[str, dict[str, str]]:
    found = {}
    for plan in plans:
        severities = {}
        for kpi in plan["kpis"]:
            spec = specs[channel_of(kpi)]
            value = spec["kpi_values"][kpi["title"]]
            severities[kpi["title"]] = severity_of(kpi, value)
        found[plan["title"]] = severities
    return found


def episode_specs(plans: list[dict], specs: dict) -> list[dict]:
    actual = actual_severities(plans, specs)
    notables = []
    for plan in plans:
        ranked = sorted(
            ((WORSE_RANK[severity], title) for title, severity in actual[plan["title"]].items()),
            reverse=True,
        )
        # Collapse duplicate fields (same severity and same value) by keeping first title of each severity+value.
        worst_title = ranked[0][1]
        worst = actual[plan["title"]][worst_title]
        kpi = next(item for item in plan["kpis"] if item["title"] == worst_title)
        value = specs[channel_of(kpi)]["kpi_values"][worst_title]
        unit = kpi.get("unit") or ""
        reading = _fmt(value)
        if worst == "normal":
            title = f"{plan['title']} — watching {worst_title}"
            description = (
                f"{plan['title']} is healthy. {worst_title} is {reading} {unit}. "
                "This low episode stays open so a quiet service still appears in Episode Review."
            )
        else:
            title = f"{plan['title']} — {worst_title} at {LABEL[worst]} severity"
            description = (
                f"{worst_title} on {plan['title']} is {reading} {unit}, in the {worst} band. "
                "Other KPIs on this service are healthier. The sample holds for the next 3 hours."
            )
        notables.append(
            {
                "service": plan["title"],
                "title": title,
                "description": description,
                "severity": ITSI_SEVERITY[worst],
                "status": plan["status"],
                "instruction": f"Open {plan['title']} and compare {worst_title} with the rest of its KPIs.",
                "kpi": worst_title,
                "band": worst,
            }
        )
        others = [name for _, name in ranked if name != worst_title and actual[plan["title"]][name] not in ("normal", worst)]
        if worst in ("high", "critical") and others:
            second = others[0]
            second_band = actual[plan["title"]][second]
            second_kpi = next(item for item in plan["kpis"] if item["title"] == second)
            second_value = specs[channel_of(second_kpi)]["kpi_values"][second]
            notables.append(
                {
                    "service": plan["title"],
                    "title": f"{plan['title']} — {second} at {LABEL[second_band]} severity",
                    "description": (
                        f"{second} is {_fmt(second_value)} {second_kpi.get('unit') or ''}. "
                        f"It is contributing to the {plan['title']} episode along with {worst_title}."
                    ),
                    "severity": ITSI_SEVERITY[second_band],
                    "status": plan["status"],
                    "instruction": f"Compare {second} with {worst_title} on {plan['title']}.",
                    "kpi": second,
                    "band": second_band,
                }
            )
    return notables


def _latest_event_time() -> datetime | None:
    try:
        rows = client.search(
            "index=tamm_feedback sourcetype=tamm:feedback | stats max(_time) as mx",
            earliest="-30d",
            latest="+4h",
        )
    except RuntimeError as exc:
        print(f"latest-event lookup skipped: {exc}")
        return None
    if not rows or rows[0].get("mx") in (None, "", "0"):
        return None
    return datetime.fromtimestamp(float(rows[0]["mx"]), timezone.utc).replace(tzinfo=None)


def _wait_for_open_episodes(minimum: int, timeout=180) -> list[dict]:
    import time

    deadline = time.time() + timeout
    latest: list[dict] = []
    while time.time() < deadline:
        _, groups = client.request(
            "GET",
            "/servicesNS/nobody/SA-ITOA/event_management_interface/notable_event_group",
            query={"limit": "200"},
        )
        groups = groups if isinstance(groups, list) else []
        latest = [group for group in groups if str(group.get("status")) != "5"]
        if len(latest) >= minimum:
            return latest
        time.sleep(5)
    return latest


def apply():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    last = _latest_event_time()
    start, end = demo_window(now, last)
    plans = assign_plans()
    specs = compile_channels(plans)
    notables = episode_specs(plans, specs)
    bands: dict[str, int] = {}
    for plan in plans:
        band = next(item["band"] for item in notables if item["service"] == plan["title"])
        bands[band] = bands.get(band, 0) + 1
    print(json.dumps({"leaf_episodes": bands, "notables": len(notables), "from": start.isoformat(), "until": end.isoformat()}, indent=2))

    ensure_index()
    events = generate_demo(start, end, plans, specs)
    print(f"demo events {len(events)}")
    sent = ingest([dict(event) for event in events])
    print(f"ingested {sent}")

    enable_service_policy()
    break_open_lab_episodes()
    created = 0
    # Post the lower-severity notable first so the episode keeps the highest severity.
    for spec in sorted(notables, key=lambda item: (item["service"], int(item["severity"]))):
        found = client.find_by_title("service", spec["service"])
        if not found:
            print(f"skip episode; service not found: {spec['service']}")
            continue
        post_notable(spec["service"], found["_key"], spec)
        created += 1
    open_groups = _wait_for_open_episodes(max(10, len(plans) // 2))
    print(json.dumps({"notables_posted": created, "open_episodes": len(open_groups)}, indent=2))
    return {"sent": sent, "notables": created, "open_episodes": len(open_groups)}
