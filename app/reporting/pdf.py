"""Renders a QualityReport into a downloadable PDF using reportlab."""

import io
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

BRAND = colors.HexColor("#7a68ff")

# Screenshots are only meaningful for scenarios that didn't cleanly pass -
# these are the statuses where TestExecutor captures a failure.png.
SCREENSHOT_STATUSES = {"FAILED", "HEALED", "ESCALATED"}


def build_report_pdf(report) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=18 * mm, bottomMargin=18 * mm,
        leftMargin=16 * mm, rightMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "AivarTitle", parent=styles["Title"], textColor=BRAND, fontSize=22,
    )
    h2 = ParagraphStyle("AivarH2", parent=styles["Heading2"], textColor=BRAND)
    body = styles["BodyText"]
    cell_style = ParagraphStyle("AivarCell", parent=styles["BodyText"], fontSize=8, leading=10)
    header_style = ParagraphStyle(
        "AivarHeader", parent=styles["BodyText"], fontSize=9, leading=11,
        textColor=colors.white, fontName="Helvetica-Bold",
    )

    def _row(values):
        """Wrap every cell in a Paragraph so long text wraps instead of overflowing."""
        return [Paragraph(str(v), cell_style) for v in values]

    def _header(values):
        return [Paragraph(str(v), header_style) for v in values]

    story = [
        Paragraph("ATOA — Autonomous Test Orchestration Agent Report", title_style),
        Spacer(1, 4 * mm),
        Paragraph(f"Target application: {report.application_url}", body),
        Paragraph(f"Run ID: {report.run_id or 'n/a'}", body),
        Paragraph(f"Risk level: <b>{report.risk}</b>", body),
        Spacer(1, 6 * mm),
        Paragraph("Summary", h2),
        Paragraph(report.summary, body),
        Spacer(1, 6 * mm),
        Paragraph("Execution Outcomes", h2),
    ]

    outcome_rows = [_header(["Metric", "Count"])]
    for label, value in [
        ("Scenarios planned", report.total_planned),
        ("Tests generated", report.total_generated),
        ("Tests executed", report.total_executed),
        ("Passed", report.passed),
        ("Healed", report.healed),
        ("Failed", report.failed),
        ("Escalated", report.escalated),
        ("Blocked", report.blocked),
        ("Coverage score", f"{report.coverage_score:.0%}"),
    ]:
        outcome_rows.append(_row([label, value]))
    outcome_table = Table(outcome_rows, colWidths=[100 * mm, 40 * mm])
    outcome_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e0ff")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f4ff")]),
    ]))
    story += [outcome_table, Spacer(1, 6 * mm)]

    if report.coverage_gaps:
        story.append(Paragraph("Coverage Gaps Remaining", h2))
        gap_rows = [_header(["Category", "Missing scenario", "Risk"])]
        for gap in report.coverage_gaps:
            gap_rows.append(_row([gap.category, gap.missing_scenario, gap.risk]))
        gap_table = Table(gap_rows, colWidths=[30 * mm, 128 * mm, 20 * mm])
        gap_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e0ff")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story += [gap_table, Spacer(1, 6 * mm)]

    if report.healer_actions:
        story.append(Paragraph("Healer Actions Taken", h2))
        for action in report.healer_actions:
            story.append(Paragraph(f"• {action}", body))
        story.append(Spacer(1, 6 * mm))

    if report.results:
        story.append(Paragraph("Scenario Outcomes", h2))
        scenario_names = {s.id: s.name for s in report.scenarios}
        result_rows = [_header(["Test ID", "Case", "Status", "Duration (ms)", "Note"])]
        for r in report.results:
            scenario_id = r.test_id.split("TC-", 1)[-1] if "TC-" in r.test_id else r.test_id
            case_name = scenario_names.get(scenario_id, "-")
            result_rows.append(_row([
                r.test_id, case_name, r.status, r.duration_ms,
                (r.error or r.healing_action or "-")[:120],
            ]))
        result_table = Table(result_rows, colWidths=[20 * mm, 40 * mm, 18 * mm, 22 * mm, 78 * mm])
        result_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e0ff")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story += [result_table, Spacer(1, 6 * mm)]

        screenshot_results = [
            r for r in report.results
            if r.status in SCREENSHOT_STATUSES
            and r.screenshot_path
            and Path(r.screenshot_path).exists()
        ]
        if screenshot_results:
            story.append(Paragraph("Failure Screenshots", h2))
            for r in screenshot_results:
                scenario_id = r.test_id.split("TC-", 1)[-1] if "TC-" in r.test_id else r.test_id
                case_name = scenario_names.get(scenario_id, r.test_id)
                story.append(Paragraph(f"<b>{r.test_id}</b> — {case_name} ({r.status})", body))
                try:
                    img = Image(r.screenshot_path, width=160 * mm, height=90 * mm, kind="proportional")
                    story.append(img)
                except Exception:
                    story.append(Paragraph("(screenshot could not be embedded)", body))
                story.append(Spacer(1, 4 * mm))

    if report.prd_gap and report.prd_gap.requirements_considered:
        story.append(Paragraph("PRD Coverage Gap Analysis", h2))
        story.append(Paragraph(
            f"{report.prd_gap.requirements_covered}/{report.prd_gap.requirements_considered} "
            "requirements matched to a test scenario.", body,
        ))
        for item in report.prd_gap.items:
            mark = "&#10003;" if item.covered else "&#10007;"
            story.append(Paragraph(f"{mark} {item.requirement}", body))

    doc.build(story)
    return buffer.getvalue()
