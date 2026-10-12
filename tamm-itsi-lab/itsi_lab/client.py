"""Splunk / ITSI REST client. Auth is token or username/password from env."""
from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CTX = ssl._create_unverified_context()


def load_dotenv(path: str | os.PathLike | None = None):
    """Load KEY=VALUE pairs from .env without adding a dependency."""
    candidates = []
    if path:
        candidates.append(Path(path))
    candidates.append(Path.cwd() / ".env")
    candidates.append(Path(__file__).resolve().parent.parent / ".env")
    seen = set()
    for env_path in candidates:
        env_path = env_path.resolve()
        if env_path in seen or not env_path.is_file():
            continue
        seen.add(env_path)
        for raw in env_path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key and key not in os.environ:
                os.environ[key] = value


def _token() -> str | None:
    if os.environ.get("SPLUNK_TOKEN"):
        return os.environ["SPLUNK_TOKEN"].strip()
    path = os.environ.get("SPLUNK_TOKEN_FILE")
    if path and Path(path).is_file():
        return Path(path).read_text().strip()
    return None


def _password() -> str | None:
    if os.environ.get("SPLUNK_PASSWORD"):
        return os.environ["SPLUNK_PASSWORD"]
    secret = Path(os.environ.get("ITSILAB_SECRET_FILE", "/opt/itsi-lab/admin.secret"))
    if secret.is_file():
        return secret.read_text().strip()
    return None


def mgmt_url() -> str:
    url = os.environ.get("SPLUNK_MGMT_URL", "").rstrip("/")
    if not url:
        raise SystemExit("Set SPLUNK_MGMT_URL, for example https://host:8089")
    return url


def request(method: str, path: str, *, query=None, form=None, json_body=None, raw=None, timeout=120):
    url = mgmt_url() + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    headers = {"Accept": "application/json"}
    token = _token()
    if token:
        headers["Authorization"] = "Bearer " + token
    else:
        user = os.environ.get("SPLUNK_USERNAME", "admin")
        pw = _password()
        if not pw:
            raise SystemExit("Set SPLUNK_TOKEN (or SPLUNK_TOKEN_FILE) or SPLUNK_PASSWORD")
        import base64

        headers["Authorization"] = "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()
    data = None
    if json_body is not None:
        data = json.dumps(json_body).encode()
        headers["Content-Type"] = "application/json"
    elif form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif raw is not None:
        data = raw if isinstance(raw, bytes) else raw.encode()
        headers["Content-Type"] = "text/plain"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=timeout) as resp:
            body = resp.read().decode()
            if not body:
                return resp.status, None
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, body
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"{method} {path} failed: {exc.code} {err[:1200]}") from exc


def get_service(key: str):
    _, body = request("GET", f"/servicesNS/nobody/SA-ITOA/itoa_interface/service/{key}")
    return body


def find_by_title(object_type: str, title: str):
    _, body = request(
        "GET",
        f"/servicesNS/nobody/SA-ITOA/itoa_interface/{object_type}",
        query={"filter": json.dumps({"title": title}), "fields": "title,_key,kpis,services_depends_on"},
    )
    if isinstance(body, list) and body:
        return body[0]
    if isinstance(body, dict) and body.get("title") == title:
        return body
    return None


def health_kpi_key(service_obj) -> str | None:
    for kpi in service_obj.get("kpis") or []:
        title = (kpi.get("title") or "").lower()
        if "health" in title or kpi.get("type") == "service_health":
            return kpi.get("_key")
        if str(kpi.get("_key", "")).startswith("SHKPI"):
            return kpi.get("_key")
    kpis = service_obj.get("kpis") or []
    return kpis[0].get("_key") if kpis else None


def dep(service_obj) -> dict:
    kpi = health_kpi_key(service_obj)
    return {"serviceid": service_obj["_key"], "kpis_depending_on": [kpi] if kpi else []}


def search(spl: str, earliest="-24h", latest="now"):
    _, job = request(
        "POST",
        "/services/search/jobs",
        form={
            "search": spl if spl.startswith("|") else f"search {spl}",
            "exec_mode": "blocking",
            "output_mode": "json",
            "earliest_time": earliest,
            "latest_time": latest,
        },
        query={"output_mode": "json"},
    )
    sid = job.get("sid") if isinstance(job, dict) else None
    if not sid:
        return []
    _, results = request(
        "GET",
        f"/services/search/jobs/{sid}/results",
        query={"output_mode": "json", "count": 100},
    )
    return (results or {}).get("results") if isinstance(results, dict) else []
