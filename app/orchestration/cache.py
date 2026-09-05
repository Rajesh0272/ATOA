"""Execution cache for AIVAR.

Stores per-URL execution artifacts (planner output, generated tests,
results, and a lightweight page fingerprint) under artifacts/<url_slug>/
so that repeat runs against an unchanged website can skip the Planner,
Coverage, and Generator LLM calls entirely and only re-execute
scenarios that previously failed/healed/escalated.
"""
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Optional

from app.models.schemas import ExecutionResult, GeneratedTest, TestPlan

ARTIFACT_ROOT = Path("artifacts")

# Statuses that must be re-verified even when the site has not changed.
RERUN_STATUSES = {"FAILED", "HEALED", "ESCALATED"}
PLANNER_VERSION = "v1"
GENERATOR_VERSION = "v1"


def url_slug(url: str) -> str:
    """Derive a stable, filesystem-safe directory name for a URL."""
    host_and_path = re.sub(r"^https?://", "", url).strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "_", host_and_path).strip("_")
    if not slug:
        slug = hashlib.sha256(url.encode()).hexdigest()[:12]
    return slug[:80]


def clear_cache(url: Optional[str] = None, artifact_root: Path = ARTIFACT_ROOT) -> list[str]:
    """Delete cached execution artifacts.

    If `url` is given, only that URL's cache directory is removed.
    Otherwise every cached URL directory under `artifact_root` is removed.
    Returns the list of directory names that were removed.
    """
    import shutil

    root = Path(artifact_root)
    if url:
        target = root / url_slug(url)
        if target.exists():
            shutil.rmtree(target)
            return [target.name]
        return []

    removed = []
    if root.exists():
        for child in root.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
                removed.append(child.name)
    return removed


class ExecutionCache:
    def __init__(self, url: str, artifact_root: Path = ARTIFACT_ROOT):
        self.url = url
        self.slug = url_slug(url)
        self.dir = Path(artifact_root) / self.slug
        self.dir.mkdir(parents=True, exist_ok=True)
        self.metadata_path = self.dir / "metadata.json"
        self.plan_path = self.dir / "planner.json"
        self.tests_dir = self.dir / "generated_tests"
        self.tests_path = self.tests_dir / "tests.json"
        self.results_path = self.dir / "results.json"
        self.report_path = self.dir / "report.json"

    # ------------------------------------------------------------------
    # Fingerprinting
    # ------------------------------------------------------------------
    def compute_fingerprint(self, obs) -> dict:
        """Build a normalized DOM fingerprint from an ApplicationObservation.

        Uses title, structural element info (tag/text/role/name/label),
        links, and forms - not raw whitespace/markup - so trivial
        re-renders don't falsely register as a website change.
        """
        normalized = json.dumps(
            {
                "title": obs.title or "",
                "elements": sorted(
                    [e.tag or "", e.text or "", e.role or "", e.name or "", e.label or ""]
                    for e in obs.elements
                ),
                "links": sorted(link or "" for link in obs.links),
                "forms": sorted(form or "" for form in obs.forms),
            },
            sort_keys=True,
        )
        dom_hash = "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return {
            "final_url": obs.url,
            "title": obs.title,
            "dom_hash": dom_hash,
            "element_count": len(obs.elements),
        }

    def website_changed(self, old_meta: Optional[dict], new_fingerprint: dict) -> bool:
        if not old_meta:
            return True
        return old_meta.get("dom_hash") != new_fingerprint.get("dom_hash")

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------
    def load_metadata(self) -> Optional[dict]:
        if not self.metadata_path.exists():
            return None
        try:
            return json.loads(self.metadata_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def load_report(self) -> Optional[dict]:
        """Load the last persisted QualityReport (as a plain dict) for this URL."""
        if not self.report_path.exists():
            return None
        try:
            return json.loads(self.report_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def load_plan(self) -> Optional[TestPlan]:
        if not self.plan_path.exists():
            return None
        try:
            return TestPlan.model_validate(json.loads(self.plan_path.read_text(encoding="utf-8")))
        except Exception:
            return None

    def load_tests(self) -> Optional[list[GeneratedTest]]:
        if not self.tests_path.exists():
            return None
        try:
            data = json.loads(self.tests_path.read_text(encoding="utf-8"))
            return [GeneratedTest.model_validate(t) for t in data]
        except Exception:
            return None

    def load_results(self) -> Optional[list[ExecutionResult]]:
        if not self.results_path.exists():
            return None
        try:
            data = json.loads(self.results_path.read_text(encoding="utf-8"))
            return [ExecutionResult.model_validate(r) for r in data]
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------
    def save_plan(self, plan: TestPlan) -> None:
        self.plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")

    def save_tests(self, tests: list[GeneratedTest]) -> None:
        self.tests_dir.mkdir(parents=True, exist_ok=True)
        self.tests_path.write_text(
            json.dumps([t.model_dump() for t in tests], indent=2), encoding="utf-8"
        )

    def save_results(self, results: list[ExecutionResult]) -> None:
        self.results_path.write_text(
            json.dumps([r.model_dump() for r in results], indent=2), encoding="utf-8"
        )

    def save_report(self, report: dict) -> None:
        """Persist the full QualityReport (as a plain dict) alongside this
        URL's other cached artifacts, so a report is always durably
        available for this URL even if the in-memory report store
        (app.reporting.store) is cleared by a server restart."""
        self.report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    def save_metadata(self, fingerprint: dict, tests: list[GeneratedTest]) -> dict:
        meta = {
            "url": self.url,
            "executed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            **fingerprint,
            "tests_generated": [t.id for t in tests],
            "results_file": "results.json",
            "planner_version": PLANNER_VERSION,
            "generator_version": GENERATOR_VERSION,
        }
        self.metadata_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return meta

    # ------------------------------------------------------------------
    # Rerun-plan helper
    # ------------------------------------------------------------------
    @staticmethod
    def scenarios_to_rerun(
        prev_results: list[ExecutionResult], credentials_available: bool
    ) -> tuple[set[str], list[ExecutionResult]]:
        """Return (test_ids_to_rerun, reused_results) per the status mapping:

        PASSED -> skip (reuse).
        HEALED -> rerun to re-verify it still passes.
        FAILED -> rerun.
        ESCALATED -> rerun (attempt healing again).
        BLOCKED -> skip unless credentials are now available.
        """
        rerun_ids: set[str] = set()
        reused: list[ExecutionResult] = []
        for r in prev_results:
            if r.status in RERUN_STATUSES:
                rerun_ids.add(r.test_id)
            elif r.status == "BLOCKED" and credentials_available:
                rerun_ids.add(r.test_id)
            else:
                reused.append(r)
        return rerun_ids, reused
