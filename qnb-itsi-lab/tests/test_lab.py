import json
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _walk(node, acc):
    acc.append(node["title"])
    for child in node.get("children") or []:
        _walk(child, acc)
    return acc


class TreeTests(unittest.TestCase):
    def setUp(self):
        self.tree = json.loads((ROOT / "config" / "tree.json").read_text())

    def test_unique_service_titles(self):
        titles = _walk(self.tree["root"], [])
        self.assertEqual(len(titles), len(set(titles)), titles)

    def test_root_and_journeys(self):
        self.assertEqual(self.tree["root"]["title"], "QNB")
        names = [child["title"] for child in self.tree["root"]["children"]]
        self.assertEqual(names[:2], ["Apply for Credit Card", "Apply for Personal Loan"])
        self.assertIn("AI Agent Observability", names)
        self.assertEqual(len(_walk(self.tree["root"], [])), 36)
        self.assertNotIn("Payment", names)
        self.assertNotIn("Payment gateway", names)

    def test_no_legacy_names(self):
        text = (ROOT / "config" / "tree.json").read_text()
        for legacy in (
            "TAMM",
            "ICP",
            "Golden Residency",
            "Entry Permit",
            "AD Police",
            "Pay Traffic Fines",
            "MOI",
            "UAE Pass",
            "Payment gateway",
            "Renew Driving License",
            "Weapon License",
            "Revenue",
        ):
            self.assertNotIn(legacy, text)


class CatalogTests(unittest.TestCase):
    def test_kpi_titles_exist_in_tree(self):
        from itsi_lab.kpis import catalog
        from itsi_lab.tree import load_tree

        titles = _walk(load_tree()["root"], [])
        missing = [name for name in catalog() if name not in titles]
        self.assertEqual(missing, [])
        for removed in ("Payment", "Payment gateway", "Revenue", "UAE Pass", "MOI"):
            self.assertNotIn(removed, catalog())

    def test_every_leaf_has_sample_kpis(self):
        from itsi_lab.kpis import catalog
        from itsi_lab.tree import load_tree

        def leaves(node):
            children = node.get("children") or []
            if not children:
                yield node["title"]
                return
            for child in children:
                yield from leaves(child)

        missing = [title for title in leaves(load_tree()["root"]) if title not in catalog()]
        self.assertEqual(missing, [])
        for title, kpis in catalog().items():
            self.assertGreaterEqual(len(kpis), 1, title)
            self.assertTrue(all('channel="' in kpi["base_search"] for kpi in kpis))


class SampleTests(unittest.TestCase):
    def test_channels_and_window(self):
        import re

        from itsi_lab.kpis import LEAF_SERVICES, catalog
        from itsi_lab.samples import generate

        now = datetime(2026, 10, 12, 12, 0, 0)
        events = generate(now)
        channels = {ev["channel"] for ev in events}
        expected = {
            "call_center",
            "survey",
            "social_media",
            "snow",
            "revenue",
            "auth_provider",
            "authentication",
            "appdynamics",
            "azure",
            "kubernetes",
        }
        self.assertTrue(expected.issubset(channels), channels)
        self.assertGreater(len(events), 1000)
        times = [ev["time"] for ev in events]
        self.assertGreaterEqual((now - min(times)).total_seconds(), 23 * 3600)
        self.assertLessEqual((now - max(times)).total_seconds(), 200)

        needed = set()
        for kpis in catalog().values():
            for kpi in kpis:
                needed.add(re.search(r'channel="([^"]+)"', kpi["base_search"]).group(1))
        self.assertTrue(needed.issubset(channels), sorted(needed - channels))
        leaf_channels = {channel for _, channel, _ in LEAF_SERVICES}
        self.assertTrue(leaf_channels.issubset(channels))
        leaf_events = [ev for ev in events if ev["channel"] in leaf_channels]
        self.assertTrue(all(ev.get("service") for ev in leaf_events))

    def test_hallucination_spike_stays_in_high_band(self):
        from itsi_lab.samples import generate_hallucination_spike

        start = datetime(2026, 10, 20, 9, 0, 0)
        events = generate_hallucination_spike(start, start + timedelta(minutes=10))
        self.assertGreater(len(events), 20)
        for event in events:
            self.assertEqual(event["channel"], "ai_agent")
            self.assertGreaterEqual(event["hallucination_pct"], 11.5)
            self.assertLess(event["hallucination_pct"], 14)

    def test_qnb_environment_samples_stay_in_band(self):
        from itsi_lab.samples import generate_qnb_environment

        start = datetime(2026, 10, 20, 9, 0, 0)
        events = generate_qnb_environment(start, start + timedelta(minutes=5))
        by_channel = {}
        for event in events:
            by_channel.setdefault(event["channel"], []).append(event)
        self.assertEqual(set(by_channel), {"adp_env_apm", "adp_env_infra", "adp_env_network"})
        for event in by_channel["adp_env_apm"]:
            self.assertGreaterEqual(event["error_pct"], 1)
            self.assertLess(event["error_pct"], 2)
            self.assertLess(event["response_ms"], 400)
        for event in by_channel["adp_env_infra"]:
            self.assertGreaterEqual(event["availability"], 99.5)
            self.assertLess(event["cpu_pct"], 70)
        for event in by_channel["adp_env_network"]:
            self.assertGreaterEqual(event["availability"], 99.5)
            self.assertLess(event["rtt_ms"], 20)


def _fake_services(titles):
    return {title: {"_key": f"key-{title}", "shkpi": f"SHKPI-key-{title}", "title": title} for title in titles}


def _images(definition):
    return [viz for viz in definition["visualizations"].values() if viz["type"] == "splunk.image"]


def _layout(definition):
    return definition["layout"]["layoutDefinitions"]["layout_1"]["options"]


class GlassTests(unittest.TestCase):
    def test_executive_binds_tree_titles(self):
        from itsi_lab.glass import DEPENDENCIES, FOCUS, JOURNEY_SERVICES, build

        fake = _fake_services(["QNB", FOCUS, *JOURNEY_SERVICES, *[t for _, t in DEPENDENCIES]])
        definition = build(fake)
        self.assertGreater(len(definition["visualizations"]), 50)
        layout = _layout(definition)
        self.assertEqual(layout["backgroundColor"], "#FFFFFF")
        self.assertEqual((layout["width"], layout["height"]), (1600, 1000))
        self.assertNotIn("backgroundImage", layout)
        images = _images(definition)
        self.assertEqual(len(images), 2)
        self.assertTrue(all(i["options"]["src"].startswith("data:image/png;base64,") for i in images))
        queries = " ".join(ds["options"].get("query", "") for ds in definition["dataSources"].values())
        self.assertIn("SHKPI-key-Apply for Credit Card", queries)
        self.assertIn("SHKPI-key-Apply for Personal Loan", queries)
        self.assertIn("SHKPI-key-QNB", queries)
        self.assertIn("SHKPI-key-APM", queries)
        self.assertIn("SHKPI-key-Auth Provider", queries)


class OpsGlassTests(unittest.TestCase):
    def test_ops_binds_tree_and_episodes(self):
        from itsi_lab.glass_ops import (
            MAIN_BRANCHES,
            PTF,
            PTF_CHILDREN,
            SHARED_NODES,
            TITLE,
            build,
            episode_table_query,
        )

        fake = _fake_services([*MAIN_BRANCHES, *SHARED_NODES, PTF, *PTF_CHILDREN])
        metrics = {
            "Completion rate": {
                "kpi": "kpi-completion",
                "service": "key-Apply for Credit Card",
                "service_title": "Apply for Credit Card",
                "name": "Apply for Credit Card - Completion rate",
            }
        }
        definition = build(fake, metrics)
        self.assertEqual(definition["title"], TITLE)
        types = {v["type"] for v in definition["visualizations"].values()}
        self.assertIn("splunk.table", types)
        layout = _layout(definition)
        self.assertEqual(layout["backgroundColor"], "#FFFFFF")
        self.assertEqual((layout["width"], layout["height"]), (1600, 1000))
        self.assertEqual(len(_images(definition)), 2)
        queries = " ".join(ds["options"].get("query", "") for ds in definition["dataSources"].values())
        self.assertIn("SHKPI-key-QNB", queries)
        self.assertIn("SHKPI-key-Apply for Personal Loan", queries)
        self.assertIn("SHKPI-key-Auth Provider", queries)
        self.assertIn("kpi-completion", queries)
        self.assertIn("itsi_notable_group_user_lookup", queries)
        self.assertIn("itsi_grouped_alerts", episode_table_query())
        table = next(v for v in definition["visualizations"].values() if v["type"] == "splunk.table")
        self.assertEqual(table["options"]["backgroundColor"], "#F8F6F2")
        self.assertEqual(table["options"]["headerBackgroundColor"], "#F1E8D4")
        urls = [
            handler["options"]["url"]
            for viz in definition["visualizations"].values()
            for handler in viz.get("eventHandlers") or []
            if handler.get("options", {}).get("url")
        ]
        self.assertTrue(urls)
        self.assertTrue(all("homeview" in url or url.endswith("/itsi_event_management") for url in urls))
        self.assertTrue(any("service=Apply%20for%20Credit%20Card" in url for url in urls))
        self.assertFalse(any("Payment" in url for url in urls))


class SourceGlassTests(unittest.TestCase):
    def test_source_tables_bind_live_services(self):
        from itsi_lab.source_glass import (
            BUSINESS_SERVICES,
            DEPENDENCIES,
            INFRA_HEALTH,
            build_business,
            build_infrastructure,
        )

        titles = set(BUSINESS_SERVICES + INFRA_HEALTH + [t for _, t in DEPENDENCIES] + ["QNB", "RUM", "Call Center"])
        services = _fake_services(titles)

        def metric(kpi, service):
            return {"kpi": kpi, "service": f"key-{service}", "service_title": service, "name": kpi}

        metrics = {
            "Completion rate": metric("kpi-completion", "Apply for Credit Card"),
            "Critical alerts": metric("kpi-alerts", "Infrastructure Observability"),
            "Network availability": metric("kpi-network", "Network"),
            "Switch availability": metric("kpi-switch", "Cisco switches"),
            "Storage capacity": metric("kpi-storage", "Storage"),
        }
        business = build_business(services, metrics)
        infra = build_infrastructure(services, metrics)
        for definition in (business, infra):
            options = _layout(definition)
            self.assertEqual(options["backgroundColor"], "#FFFFFF")
            self.assertFalse(options.get("backgroundImage"))
            self.assertEqual((options["width"], options["height"]), (1600, 1000))
            self.assertEqual(len(_images(definition)), 2)
        business_queries = " ".join(ds["options"].get("query", "") for ds in business["dataSources"].values())
        infra_queries = " ".join(ds["options"].get("query", "") for ds in infra["dataSources"].values())
        self.assertIn("SHKPI-key-Apply for Credit Card", business_queries)
        self.assertIn("kpi-completion", business_queries)
        self.assertIn("SHKPI-key-Infrastructure Observability", infra_queries)
        for kpi in ("kpi-network", "kpi-switch", "kpi-alerts"):
            self.assertIn(kpi, infra_queries)
        infra_urls = [
            handler["options"]["url"]
            for viz in infra["visualizations"].values()
            for handler in viz.get("eventHandlers") or []
            if handler.get("options", {}).get("url")
        ]
        self.assertTrue(any("service=Cisco%20switches" in url and "homeview" in url for url in infra_urls))
        self.assertNotIn("service_analyzer", " ".join(infra_urls))

    def test_titles_use_qnb(self):
        from itsi_lab import glass, glass_ops, source_glass

        self.assertEqual(glass.TITLE, "QNB Business & digital services")
        self.assertEqual(glass_ops.TITLE, "QNB Operations & episodes")
        self.assertEqual(source_glass.BUSINESS_TITLE, "QNB | Business and digital service health")
        self.assertEqual(source_glass.INFRA_TITLE, "QNB | Infrastructure and SaaS health")


class DemoTests(unittest.TestCase):
    def test_band_values_land_in_severity(self):
        from itsi_lab.demo import band_value, severity_of
        from itsi_lab.kpis import catalog

        for kpis in catalog().values():
            for kpi in kpis:
                for severity in ("normal", "low", "medium", "high", "critical"):
                    value = band_value(kpi, severity)
                    self.assertEqual(severity_of(kpi, value), severity, f"{kpi['title']} {severity} -> {value}")

    def test_demo_mixes_every_leaf_and_covers_the_window(self):
        from itsi_lab.demo import (
            actual_severities,
            assign_plans,
            compile_channels,
            demo_window,
            episode_specs,
            generate_demo,
            leaf_titles,
        )

        now = datetime(2026, 10, 20, 7, 0, 0)
        last = datetime(2026, 10, 19, 20, 9, 10)
        start, end = demo_window(now, last)
        self.assertGreaterEqual((end - now).total_seconds(), 3 * 3600)
        self.assertGreater(start, last)
        plans = assign_plans()
        self.assertEqual([plan["title"] for plan in plans], leaf_titles())
        specs = compile_channels(plans)
        actual = actual_severities(plans, specs)
        rank = {"normal": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
        worst = [max(actual[plan["title"]].values(), key=rank.get) for plan in plans]
        self.assertGreaterEqual(len(set(worst)), 4, sorted(set(worst)))
        self.assertGreaterEqual(worst.count("normal"), 8)
        self.assertTrue(any(band in ("high", "critical") for band in worst))
        notables = episode_specs(plans, specs)
        self.assertEqual({item["service"] for item in notables}, set(leaf_titles()))
        self.assertTrue(all(int(item["severity"]) >= 3 for item in notables))
        events = generate_demo(start, start + timedelta(minutes=15), plans, specs)
        channels = {event["channel"] for event in events}
        self.assertTrue(set(specs).issubset(channels))
        times = [event["time"] for event in events]
        self.assertGreaterEqual(min(times), start)
        self.assertLess(max(times), start + timedelta(minutes=15))


class ExportTests(unittest.TestCase):
    def test_export_strips_host_ids_and_health_kpi(self):
        from itsi_lab.export_config import include_glass_table, portable_glass, portable_service, rewrite

        labels = {
            "svc-1111-aaaa": "Microsoft Teams",
            "kpi-2222-bbbb": "Microsoft Teams / Active users",
        }
        raw = (
            "https://example-host.splunk.show/en-US/app/itsi/homeview?"
            "serviceId=svc-1111-aaaa&kpi=kpi-2222-bbbb"
        )
        self.assertEqual(
            rewrite(raw, labels),
            "/en-US/app/itsi/homeview?serviceId={{Microsoft Teams}}&kpi={{Microsoft Teams / Active users}}",
        )
        service = portable_service(
            {
                "_key": "svc-1111-aaaa",
                "title": "Microsoft Teams",
                "description": "SaaS",
                "services_depends_on": [],
                "kpis": [
                    {"_key": "SHKPI-1", "type": "service_health", "title": "ServiceHealthScore", "base_search": "secret"},
                    {
                        "title": "Active users",
                        "base_search": "index=tamm_feedback svc-1111-aaaa",
                        "unit": "users",
                        "aggregate_statop": "avg",
                    },
                ],
            },
            labels,
        )
        self.assertEqual([kpi["title"] for kpi in service["kpis"]], ["Active users"])
        self.assertNotIn("svc-1111-aaaa", service["kpis"][0]["base_search"])
        glass = portable_glass({"title": "QNB", "description": "", "definition": {"url": raw}, "_key": "gt"}, labels)
        self.assertNotIn("_key", glass)
        self.assertNotIn("splunk.show", json.dumps(glass))
        self.assertTrue(include_glass_table("QNB Operations & episodes"))
        self.assertFalse(include_glass_table("Generic POC Glass Table"))


class DrilldownTests(unittest.TestCase):
    def test_service_link_matches_teams_drilldown(self):
        import os

        from itsi_lab.glass import episode_review_link, service_link

        os.environ.pop("SPLUNK_WEB_URL", None)
        relative = service_link("6545c512-045a-4c75-ba1e-9b2e2e549c48", "Microsoft Teams")
        self.assertTrue(relative.startswith("/en-US/app/itsi/homeview?"))
        self.assertNotIn("splunk.show", relative)
        os.environ["SPLUNK_WEB_URL"] = "https://splunk.example"
        url = service_link("6545c512-045a-4c75-ba1e-9b2e2e549c48", "Microsoft Teams")
        self.assertEqual(
            url,
            "https://splunk.example/en-US/app/itsi/homeview?"
            "earliest=-24h%40h&latest=now&view=standard&viewType=service_topology&kpi=&source="
            "&service=Microsoft%20Teams&serviceId=6545c512-045a-4c75-ba1e-9b2e2e549c48"
            "&sidePanelTab=kpis-and-episodes",
        )
        self.assertTrue(episode_review_link().endswith("/en-US/app/itsi/itsi_event_management"))
        os.environ.pop("SPLUNK_WEB_URL", None)


if __name__ == "__main__":
    unittest.main()
