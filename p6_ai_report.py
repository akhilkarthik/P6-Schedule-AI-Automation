#!/usr/bin/env python3
"""P6 Schedule AI Automation.

Reads a Primavera P6 .xer schedule, analyses it, and uses an AI layer to write
the project-controls narrative a planner would normally write by hand. Outputs
a professional PDF report and prints the narrative to the terminal.

Usage:
    python p6_ai_report.py sample_schedule.xer
    python p6_ai_report.py schedule.xer --mode api -o report.pdf

Modes:
    mock  (default)  generate the narrative offline from the metrics (no key)
    api              call a language model (needs ANTHROPIC_API_KEY)
"""

import argparse
import sys

from analyze import analyze
from ai_engine import generate_narrative


def build_pdf(facts, narrative, xer_name, out_path):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    NAVY = colors.HexColor("#1F4E79")
    GREEN = colors.HexColor("#1AAB40")
    AMBER = colors.HexColor("#D9B300")
    RED = colors.HexColor("#D64554")
    GREY = colors.HexColor("#5A6B5A")
    LIGHT = colors.HexColor("#EAF3E6")

    verdict_color = {"On Track": GREEN, "At Risk": AMBER, "Critical": RED}.get(
        facts["verdict"], GREY)

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Title"], textColor=NAVY,
                        fontSize=22, spaceAfter=2)
    sub = ParagraphStyle("sub", parent=styles["Normal"], textColor=GREY,
                         fontSize=10, spaceAfter=14)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=NAVY,
                        fontSize=13, spaceBefore=12, spaceAfter=4)
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=10,
                          textColor=colors.HexColor("#24212E"), leading=15)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8,
                           textColor=GREY, leading=11)

    doc = SimpleDocTemplate(out_path, pagesize=A4,
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=18 * mm, bottomMargin=16 * mm)
    story = []

    story.append(Paragraph("P6 Schedule — AI Narrative Report", h1))
    story.append(Paragraph(
        f"Project: {facts['project_name']} &nbsp;|&nbsp; File: {xer_name} "
        f"&nbsp;|&nbsp; Generated: {facts['generated']}", sub))

    # score banner
    banner = Table([[
        Paragraph("<b>Schedule Health</b>", body),
        Paragraph(f"<font size=24 color='{verdict_color.hexval()}'>"
                  f"<b>{facts['health_score']}/100</b></font>", body),
        Paragraph(f"<font color='{verdict_color.hexval()}'><b>"
                  f"{facts['verdict']}</b></font><br/>"
                  f"<font size=8 color='#5A6B5A'>"
                  f"{facts['avg_percent_complete']}% complete &nbsp; "
                  f"{facts['activity_count']} activities</font>", body),
    ]], colWidths=[50 * mm, 45 * mm, 75 * mm])
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
    ]))
    story.append(banner)

    # AI narrative
    story.append(Paragraph("AI-Generated Narrative", h2))
    for line in narrative.split("\n"):
        if not line.strip():
            story.append(Spacer(1, 5))
        elif line.strip().startswith("-"):
            story.append(Paragraph("&bull; " + line.strip()[1:].strip(), body))
        elif line.endswith(":"):
            story.append(Paragraph(f"<b>{line}</b>", body))
        else:
            story.append(Paragraph(line, body))

    # supporting metrics
    story.append(Paragraph("Supporting Metrics", h2))
    data = [
        ["Metric", "Value"],
        ["Activities", str(facts["activity_count"])],
        ["Relationships", str(facts["relationship_count"])],
        ["Overall % complete", f"{facts['avg_percent_complete']}%"],
        ["Completed / In-progress / Not started",
         f"{facts['completed']} / {facts['in_progress']} / {facts['not_started']}"],
        ["Negative float activities", str(facts["negative_float_count"])],
        ["High float (>44d)", str(facts["high_float_count"])],
        ["Open ends", str(facts["open_ends_count"])],
        ["Leads (negative lag)", str(facts["leads_count"])],
        ["Hard constraints", str(facts["hard_constraints_count"])],
    ]
    tbl = Table(data, colWidths=[95 * mm, 75 * mm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#F4F8F2")]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#D5E3D0")),
    ]))
    story.append(tbl)

    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Generated by P6 Schedule AI Automation. The narrative is produced by "
        "an AI layer from verified schedule metrics and should be reviewed by "
        "the responsible planner before issue.", small))

    doc.build(story)


def main():
    ap = argparse.ArgumentParser(description="AI-generated narrative report for a P6 schedule")
    ap.add_argument("xer", help="Path to the .xer file")
    ap.add_argument("-o", "--output", default="p6_ai_report.pdf")
    ap.add_argument("--mode", choices=["mock", "api"], default="mock",
                    help="mock (offline, default) or api (needs ANTHROPIC_API_KEY)")
    args = ap.parse_args()

    try:
        facts = analyze(args.xer)
    except FileNotFoundError:
        print(f"Error: file not found: {args.xer}")
        sys.exit(1)

    try:
        narrative = generate_narrative(facts, mode=args.mode)
    except RuntimeError as e:
        print(f"Error: {e}")
        sys.exit(1)

    print("\n" + "=" * 68)
    print(f"  {facts['project_name']}  —  AI Schedule Narrative ({args.mode} mode)")
    print("=" * 68 + "\n")
    print(narrative)
    print("\n" + "=" * 68)

    build_pdf(facts, narrative, args.xer.split("/")[-1], args.output)
    print(f"\nPDF report written to: {args.output}\n")


if __name__ == "__main__":
    main()
