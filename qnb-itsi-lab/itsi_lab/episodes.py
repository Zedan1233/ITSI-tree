"""Create ITSI notable events that aggregate into service episodes."""
from __future__ import annotations

import json
import time

from . import client

SERVICE_POLICY = "itsi_default_episodes_by_itsi_service_policy"

# service title -> episode story
STORIES = {
    "Apply for Credit Card": [
        {
            "title": "Apply for Credit Card — completion rate collapsed",
            "description": "Successful credit-card applications dropped in the last 3 hours. Failed and incomplete applications are elevated.",
            "severity": "6",
            "instruction": "Check Completion rate KPI, APM, and Auth Provider session establish rate.",
        },
        {
            "title": "Apply for Credit Card — incomplete applications spike",
            "description": "Applicants start the credit-card journey and drop before confirmation. Incomplete applications rose with Auth Provider failures.",
            "severity": "5",
            "instruction": "Correlate incomplete applications with Auth Provider session failures.",
        },
        {
            "title": "Apply for Credit Card — call-center abandonment surge",
            "description": "Inbound call volume and abandonment increased as customers could not complete credit-card applications.",
            "severity": "5",
            "instruction": "Review Call Center abandonment and repeat-contact KPIs.",
        },
        {
            "title": "Apply for Credit Card — P1/P2 incidents opened",
            "description": "ServiceNow P1/P2 rate for QNB-CreditCard increased. MTTA and aged tickets are up.",
            "severity": "6",
            "instruction": "Open SNOW KPIs and the related change-failure rate.",
        },
        {
            "title": "Apply for Credit Card — negative social mentions",
            "description": "Public posts about failed QNB credit-card applications are trending negative.",
            "severity": "4",
            "instruction": "Review Social Media negative sentiment and SLA breach KPIs.",
        },
    ],
    "Infrastructure Observability": [
        {
            "title": "Infrastructure — Kubernetes CrashLoop and NotReady nodes",
            "description": "CrashLooping pods and NotReady nodes are impacting QNB platform workloads.",
            "severity": "6",
            "instruction": "Open Kubernetes CrashLooping Pods, Node NotReady, and Ingress 5xx.",
        },
        {
            "title": "Infrastructure — Azure App Service availability drop",
            "description": "Azure App Service availability fell and monitor ingest delay increased.",
            "severity": "5",
            "instruction": "Review Azure App Service Availability and Unhealthy Resources.",
        },
        {
            "title": "Infrastructure — AppDynamics open problems and BT errors",
            "description": "Business-transaction error rate and open problems increased on instrumented QNB apps.",
            "severity": "5",
            "instruction": "Review AppDynamics BT Error Rate, Open Problems, and dropped agents.",
        },
    ],
}


def enable_service_policy():
    _, policy = client.request(
        "GET",
        f"/servicesNS/nobody/SA-ITOA/event_management_interface/notable_event_aggregation_policy/{SERVICE_POLICY}",
    )
    if str(policy.get("disabled")) in ("0", "False", "false"):
        print("aggregation policy already enabled: Default Episodes by ITSI Service")
        return
    policy["disabled"] = 0
    client.request(
        "POST",
        f"/servicesNS/nobody/SA-ITOA/event_management_interface/notable_event_aggregation_policy/{SERVICE_POLICY}",
        json_body=policy,
    )
    print("enabled aggregation policy: Default Episodes by ITSI Service")


def post_notable(service_title: str, service_id: str, event: dict) -> str:
    payload = {
        "title": event["title"],
        "description": event["description"],
        "severity": event["severity"],
        "status": str(event.get("status") or "1"),
        "owner": "unassigned",
        "source": f"qnb_lab:{service_title}",
        "serviceid": service_id,
        "itsi_service_id": service_id,
        "service_ids": service_id,
        "service_name": service_title,
        "instruction": event.get("instruction", ""),
        "drilldown_search": event.get("drilldown_search")
        or 'index=tamm_feedback sourcetype="tamm:feedback" | search journey=* ',
    }
    _, body = client.request(
        "POST",
        "/servicesNS/nobody/SA-ITOA/event_management_interface/notable_event",
        json_body=payload,
    )
    key = body.get("_key") if isinstance(body, dict) else body
    print(f"  notable {event['title']} -> {key}")
    return str(key)


def comment_episode(group_key: str, text: str):
    try:
        client.request(
            "POST",
            "/servicesNS/nobody/SA-ITOA/event_management_interface/notable_event_comment",
            json_body={"event_id": group_key, "comment": text, "is_group": 1},
        )
        print(f"  comment on {group_key}")
    except RuntimeError as exc:
        print(f"  comment skipped: {exc}")


def wait_for_groups(service_ids: set[str], timeout=90) -> list[dict]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        _, groups = client.request(
            "GET",
            "/servicesNS/nobody/SA-ITOA/event_management_interface/notable_event_group",
            query={"limit": "50"},
        )
        groups = groups if isinstance(groups, list) else []
        # groups from the user collection are thin; also search notable events for group ids
        if groups:
            return groups
        time.sleep(5)
    return []


def break_open_lab_episodes():
    _, groups = client.request(
        "GET",
        "/servicesNS/nobody/SA-ITOA/event_management_interface/notable_event_group",
        query={"limit": "50"},
    )
    for g in groups if isinstance(groups, list) else []:
        key = g.get("_key")
        if not key:
            continue
        if str(g.get("status")) == "5":
            continue
        try:
            client.request(
                "POST",
                "/servicesNS/nobody/SA-ITOA/event_management_interface/notable_event_group",
                json_body={
                    "_key": key,
                    "status": "5",
                    "title": g.get("title") or "QNB lab episode",
                    "description": "Closed so new service episodes can open",
                    "severity": str(g.get("severity") or "1"),
                    "owner": g.get("owner") or "unassigned",
                },
                query={"break_group_policy_id": "itsi_default_policy"},
            )
            print(f"broke episode {key}")
        except RuntimeError as exc:
            print(f"break skipped {key}: {exc}")


def apply():
    enable_service_policy()
    break_open_lab_episodes()
    created = []
    for title, events in STORIES.items():
        found = client.find_by_title("service", title)
        if not found:
            print(f"skip episodes; service not found: {title}")
            continue
        print(f"episode notables for {title} ({found['_key']})")
        for ev in events:
            created.append((title, found["_key"], post_notable(title, found["_key"], ev)))
    print(json.dumps({"created_notables": len(created)}, indent=2))

    print("waiting for Rules Engine to open episodes...")
    groups = wait_for_groups({sid for _, sid, _ in created})
    print(f"episode groups visible: {len(groups)}")

    # Comment the newest groups that mention our services, if titles exist
    for g in groups:
        key = g.get("_key")
        title = g.get("title") or ""
        if key and any(s in title for s in STORIES):
            comment_episode(
                key,
                "Generated from the QNB lab last-3-hour degradation scenario. "
                "Health scores and sample data are on the QNB service tree / glass table.",
            )
    return created
