# TAMM Splunk ITSI lab

Portable lab that recreates the TAMM service tree, sample events, and KPI thresholds on **any** Splunk Enterprise + ITSI instance.

Services are matched by **title**, not by `_key`. Nothing in this repo is bound to a Splunk Show host, REST token, or instance-specific UUID.

## What you get

```
TAMM
 ├── AD Police
 │    ├── Pay Traffic Fines
 │    │    ├── APM / RUM / SNOW / Revenue
 │    │    └── Feedback → Call Center, Survey, Social Media
 │    ├── Get a Driver Licensing   (qualified leaf titles)
 │    ├── Vehicle Accident History (qualified leaf titles)
 │    ├── Database
 │    └── AD-Connect Endpoints
 ├── AD Judicial Department
 ├── Department of Health
 ├── Authentication → UAE Pass
 └── Infrastructure Observability → AppDynamics, Azure, Kubernetes
```

ITSI requires unique service titles. The first journey (`Pay Traffic Fines`) uses short names (`APM`, `Feedback`, `Call Center`). Other journeys use qualified titles such as `APM (Get a Driver Licensing)`.

Sample data shares **one incident narrative**:

- Hours −24 to −3: healthy baseline
- Last 3 hours: degradation (volume, errors, latency, CSAT, P1/P2, payment failures)

Events go to index `tamm_feedback`, sourcetype `tamm:feedback`, as `TIMESTAMP JSON`. KPI ad hoc searches `rex` the JSON then `spath`.

## Prerequisites

- Splunk Enterprise with ITSI installed and licensed
- A REST token (Settings → Tokens) with permission to write ITSI objects and ingest events
- Python 3.10+ (stdlib only; no pip packages)

## Configure

```bash
cp .env.example .env
```

Edit `.env`:

```
SPLUNK_MGMT_URL=https://YOUR-INSTANCE:8089
SPLUNK_TOKEN=eyJ...
TAMM_SAMPLE_INDEX=tamm_feedback
TAMM_SAMPLE_SOURCETYPE=tamm:feedback
```

Alternatively export `SPLUNK_TOKEN_FILE` pointing at a file that contains only the token (mode 600). Do not commit `.env`, `*.token`, or `*.secret`.

## Seed a new instance

```bash
python -m itsi_lab ping
python -m itsi_lab seed
```

`seed` runs, in order:

1. `apply-tree` — upsert entities + services, wire `services_depends_on`
2. `ingest-samples` — create the index if needed, then ingest ~24h of events
3. `apply-kpis` — attach KPIs on leaf services (Call Center, Survey, Social Media, SNOW, Revenue, UAE Pass, Authentication, AppDynamics, Azure, Kubernetes, Database, AD-Connect Endpoints)

ITSI KPI searches backfill `-24h`. Wait a few minutes, then open **Service Analyzer**. Parent health comes from child Service Health Score KPIs; leaf urgency is set so a few bad leaves do not paint the whole tree red.

You can run the steps separately:

```bash
python -m itsi_lab apply-tree
python -m itsi_lab ingest-samples
python -m itsi_lab apply-kpis
```

Re-running `apply-tree` / `apply-kpis` is idempotent (match by title, replace lab KPIs by title, keep Service Health Score). Re-running `ingest-samples` **appends** events; the instance needs `| delete` rights if you want a clean rewind.

## Auth

Preferred: Bearer token (`SPLUNK_TOKEN` or `SPLUNK_TOKEN_FILE`).

Fallback: `SPLUNK_USERNAME` + `SPLUNK_PASSWORD`. TLS certificate verification is disabled so lab hosts with self-signed certs work.

## Layout

```
config/tree.json     declarative service tree
itsi_lab/client.py   REST client
itsi_lab/tree.py     entities + services + dependencies
itsi_lab/samples.py  24h / last-3h sample generator
itsi_lab/kpis.py     KPI catalog + TVT thresholds
```

## Tests (no Splunk required)

```bash
python -m unittest discover -s tests -v
```
