from fastapi import FastAPI, HTTPException, UploadFile, Form, File
from fastapi.responses import HTMLResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from typing import Optional

from app.orchestration.orchestrator import AIVAROrchestrator
from app.orchestration.cache import clear_cache, ExecutionCache
from app.browser.explorer import WebsiteUnreachableError
from app.models.schemas import TestCredentials
from app.reporting import store, pdf as pdf_report

app = FastAPI(title="ATOA Autonomous Test Orchestration Agent")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
def home():
    return FileResponse("static/index.html")


@app.post("/run")
def run(
    url: str = Form(...),
    username: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    parallel: bool = Form(True),
    prd_file: Optional[UploadFile] = File(None),
):
    # This is a plain (non-async) route on purpose: FastAPI/Starlette runs
    # sync def routes in a worker thread, which is required because the
    # orchestrator pipeline uses Playwright's *synchronous* API internally.
    # Calling that blocking sync API directly from an `async def` route
    # would execute it on the event loop thread and raise
    # "Sync API inside asyncio loop".
    try:
        credentials = (
            TestCredentials(username=username, password=password)
            if username and password
            else None
        )
        prd_text = None
        if prd_file is not None and prd_file.filename:
            raw = prd_file.file.read()
            try:
                prd_text = raw.decode("utf-8", errors="ignore")
            except Exception:
                prd_text = None
        report = AIVAROrchestrator().run(
            url, credentials, prd_text=prd_text, intent=description or None, parallel=parallel
        )
        store.save(report)
        return report.model_dump()
    except WebsiteUnreachableError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cache/clear")
def cache_clear(url: Optional[str] = Form(None)):
    """Clear cached execution artifacts (planner/generator/results/fingerprint).

    If `url` is supplied, only that URL's cache directory is removed so the
    next run for it executes the full Planner->Coverage->Generator pipeline.
    If omitted, every cached URL is cleared.
    """
    removed = clear_cache(url or None)
    return {"cleared": removed, "count": len(removed)}


@app.get("/cache/report")
def cache_report(url: str):
    """Return the last persisted report for a URL directly from its cache
    directory, without invoking the Planner/Coverage/Generator/Executor or
    any AI model. Useful for redisplaying a prior run's report (e.g. after
    a server restart cleared the in-memory report store)."""
    report = ExecutionCache(url).load_report()
    if report is None:
        raise HTTPException(status_code=404, detail="No cached report found for this URL")
    from app.models.schemas import QualityReport
    store.save(QualityReport.model_validate(report))
    return report


@app.get("/reports")
def list_reports():
    return [
        {
            "run_id": r.run_id,
            "application_url": r.application_url,
            "risk": r.risk,
            "created_at": r.created_at,
            "passed": r.passed,
            "failed": r.failed,
        }
        for r in store.all_reports()
    ]


@app.get("/report/{run_id}/json")
def report_json(run_id: str):
    report = store.get(run_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report.model_dump()


@app.get("/report/{run_id}/pdf")
def report_pdf(run_id: str):
    report = store.get(run_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    pdf_bytes = pdf_report.build_report_pdf(report)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="aivar-report-{run_id}.pdf"'},
    )


@app.get("/report/{run_id}/screenshot/{test_id}")
def report_screenshot(run_id: str, test_id: str):
    """Serve the failure screenshot captured for a specific scenario
    (FAILED/HEALED/ESCALATED) in a given run, so the dashboard/shared
    report page can show it and the PDF can embed it. Scoped to the
    report's own results so a test_id can't be used to read arbitrary
    files off disk."""
    report = store.get(run_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    result = next((r for r in report.results if r.test_id == test_id), None)
    if not result or not result.screenshot_path:
        raise HTTPException(status_code=404, detail="No screenshot available for this test")
    path = Path(result.screenshot_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Screenshot file not found")
    return FileResponse(str(path), media_type="image/png")


@app.get("/report/{run_id}", response_class=HTMLResponse)
def report_view(run_id: str):
    report = store.get(run_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse("static/report.html")
