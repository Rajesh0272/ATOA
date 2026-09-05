"""Renders a QualityReport into a downloadable PDF using reportlab."""

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

BRAND = colors.HexColor("#7a68ff")


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

    story = [
        Paragraph("AIVAR — Autonomous Test Quality Report", title_style),
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

    outcome_rows = [["Metric", "Count"]]
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
        outcome_rows.append([label, str(value)])
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
        gap_rows = [["Category", "Missing scenario", "Risk"]]
        for gap in report.coverage_gaps:
            gap_rows.append([gap.category, gap.missing_scenario, gap.risk])
        gap_table = Table(gap_rows, colWidths=[35 * mm, 90 * mm, 20 * mm])
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
        result_rows = [["Test ID", "Case", "Status", "Duration (ms)", "Note"]]
        for r in report.results:
            scenario_id = r.test_id.split("TC-", 1)[-1] if "TC-" in r.test_id else r.test_id
            case_name = scenario_names.get(scenario_id, "-")
            result_rows.append([r.test_id, case_name, r.status, str(r.duration_ms), (r.error or r.healing_action or "-")[:60]])
        result_table = Table(result_rows, colWidths=[22 * mm, 45 * mm, 18 * mm, 22 * mm, 38 * mm])
        result_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e0ff")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story += [result_table, Spacer(1, 6 * mm)]

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
