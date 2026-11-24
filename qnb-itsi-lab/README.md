# QNB Splunk ITSI lab

Portable configuration for the QNB service tree, KPI thresholds, and glass tables. It can be applied to any Splunk Enterprise + ITSI instance.

Services are matched by **title**, not by `_key`. This repo does not contain indexed events, episodes, REST tokens, or instance-specific ids.

## Apply

```bash
cp .env.example .env
python -m itsi_lab ping
python -m itsi_lab apply-config
```

`apply-config` creates the service tree in `config/tree.json`, the KPI thresholds on each service, and four glass tables:

- QNB Business & digital services
- QNB Operations & episodes
- QNB | Business and digital service health
- QNB | Infrastructure and SaaS health

Every glass table uses the same 1600x1000 frame: white page, off-white tiles, cream nested tiles, logo and watermark, five summary tiles, three panels, and a footer.

Optional data, after the configuration is in place:

```bash
python -m itsi_lab ingest-samples   # 24 hours of events
python -m itsi_lab demo             # forward KPI data plus one episode per leaf
ITSI_LAB_DEMO_SEVERITY=critical python -m itsi_lab demo   # every leaf KPI and episode at Critical
```

## Service tree

```
QNB
 ├── Apply for Credit Card
 │    ├── APM / RUM / SNOW
 │    ├── Card eligibility service / Card printing service
 │    └── Feedback → Call Center, Survey, Social Media
 ├── Apply for Personal Loan
 │    └── the same children, suffixed "(Apply for Personal Loan)"
 ├── Authentication → Auth Provider
 ├── Infrastructure Observability
 │    ├── AppDynamics / Azure / Kubernetes
 │    ├── Network → Cisco switches, NetFlow, Packet inspection, Cisco firewall, SD-WAN
 │    ├── Storage → PowerMax arrays
 │    └── SaaS services → Microsoft Teams, Office 365, Cisco Webex
 └── AI Agent Observability
```

ITSI requires unique service titles, which is why the Apply for Personal Loan children carry a suffix.

## Configure

```
SPLUNK_MGMT_URL=https://YOUR-INSTANCE:8089
SPLUNK_TOKEN=eyJ...
```

Prefer `SPLUNK_TOKEN_FILE` (mode 600) over putting the token in `.env`. Username and password (`SPLUNK_USERNAME`, `SPLUNK_PASSWORD`) also work. Do not commit `.env`, `*.token`, or `*.secret`. If only the web port (443) is reachable, set `SPLUNK_VIA_WEB=1`, `SPLUNK_WEB_URL`, `SPLUNK_USERNAME` and `SPLUNK_PASSWORD`; the client then logs in to Splunk Web and calls REST through `/en-US/splunkd/__raw`.

## Layout

```
config/tree.json          declarative service tree
itsi_lab/client.py        REST client
itsi_lab/tree.py          entities, services, and dependencies
itsi_lab/kpis.py          KPI catalog and thresholds
itsi_lab/glass.py         shared glass frame and the executive table
itsi_lab/glass_ops.py     operations table
itsi_lab/source_glass.py  business and infrastructure tables
itsi_lab/samples.py       sample-event generator
itsi_lab/demo.py          forward data and episodes
assets/                   QNB logo and watermark (placeholder wordmark)
```

## Tests (no Splunk required)

```bash
python -m unittest discover -s tests -v
```
