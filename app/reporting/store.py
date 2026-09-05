"""In-memory store for completed AIVAR quality reports.

Reports are kept in-memory only (no external persistence) so that a run's
result can be revisited via the dashboard, a shareable report URL, a QR
code, or a downloadable PDF without re-running the pipeline.
"""

from app.models.schemas import QualityReport

_REPORTS: dict[str, QualityReport] = {}


def save(report: QualityReport) -> QualityReport:
    _REPORTS[report.run_id] = report
    return report


def get(run_id: str) -> QualityReport | None:
    return _REPORTS.get(run_id)


def all_reports() -> list[QualityReport]:
    return sorted(_REPORTS.values(), key=lambda r: r.created_at, reverse=True)
