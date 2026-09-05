"""Persistence for completed AIVAR quality reports.

Reports are always kept in an in-process dict as a fast path. On a host
that runs a single long-lived process (local dev, a Docker container, a
VM), that alone is sufficient - a report saved during a POST /run request
is immediately visible to a later GET /report/{run_id} in the same
process.

On a stateless host such as Vercel's Python serverless functions, a later
request can land on a *different* instance whose in-memory dict never
saw that report, which surfaces to users as a spurious "Report not
found" for a run that clearly just completed. To fix that without
requiring a different hosting model, we optionally also persist reports
to Vercel KV (Upstash Redis, reachable over its REST API so no
persistent TCP connection is needed from a serverless function) whenever
KV_REST_API_URL / KV_REST_API_TOKEN are configured. If they are not
configured, behavior is identical to the old in-memory-only store.
"""
import json
import urllib.error
import urllib.request
from urllib.parse import quote

from app.config import settings
from app.models.schemas import QualityReport

_REPORTS: dict[str, QualityReport] = {}

_INDEX_KEY = "aivar:reports:index"
_MAX_INDEX_ENTRIES = 50
_REPORT_KEY_PREFIX = "aivar:report:"


def _kv_configured() -> bool:
    return bool(settings.KV_REST_API_URL and settings.KV_REST_API_TOKEN)


def _kv_request(method: str, path: str, body: bytes | None = None) -> dict | None:
    url = f"{settings.KV_REST_API_URL.rstrip('/')}/{path}"
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"Bearer {settings.KV_REST_API_TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # best-effort remote persistence, never fatal
        print(f"[WARN] Vercel KV request failed ({path}): {exc}")
        return None


def _kv_set(key: str, value: str) -> None:
    _kv_request("POST", f"set/{quote(key, safe='')}", body=value.encode("utf-8"))


def _kv_get(key: str) -> str | None:
    result = _kv_request("GET", f"get/{quote(key, safe='')}")
    if not result:
        return None
    return result.get("result")


def _update_index(entry: dict) -> None:
    raw = _kv_get(_INDEX_KEY)
    try:
        index = json.loads(raw) if raw else []
    except Exception:
        index = []
    index = [e for e in index if e.get("run_id") != entry["run_id"]]
    index.insert(0, entry)
    _kv_set(_INDEX_KEY, json.dumps(index[:_MAX_INDEX_ENTRIES]))


def save(report: QualityReport) -> QualityReport:
    _REPORTS[report.run_id] = report
    if _kv_configured():
        _kv_set(f"{_REPORT_KEY_PREFIX}{report.run_id}", report.model_dump_json())
        _update_index(
            {
                "run_id": report.run_id,
                "application_url": report.application_url,
                "risk": report.risk,
                "created_at": report.created_at,
                "passed": report.passed,
                "failed": report.failed,
            }
        )
    return report


def get(run_id: str) -> QualityReport | None:
    if run_id in _REPORTS:
        return _REPORTS[run_id]
    if _kv_configured():
        raw = _kv_get(f"{_REPORT_KEY_PREFIX}{run_id}")
        if raw:
            try:
                report = QualityReport.model_validate_json(raw)
            except Exception as exc:
                print(f"[WARN] Failed to parse cached report {run_id} from KV: {exc}")
                return None
            _REPORTS[run_id] = report
            return report
    return None


def all_reports() -> list[QualityReport]:
    if _kv_configured():
        raw = _kv_get(_INDEX_KEY)
        if raw:
            try:
                index = json.loads(raw)
            except Exception as exc:
                print(f"[WARN] Failed to parse KV report index: {exc}")
                index = []
            merged = [r for r in (get(e["run_id"]) for e in index) if r is not None]
            if merged:
                return sorted(merged, key=lambda r: r.created_at, reverse=True)
    return sorted(_REPORTS.values(), key=lambda r: r.created_at, reverse=True)
