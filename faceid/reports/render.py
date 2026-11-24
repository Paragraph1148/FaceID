"""Writing a report Table as a file (F6.2): xlsx and CSV through Pandas, PDF through ReportLab.

All three are written from the same Table, so they contain the same rows by construction.
"""

import io

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from reportlab.platypus import Table as PdfTable
from reportlab.platypus import TableStyle

from faceid.reports.tables import Table

FORMATS = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
    "csv": "text/csv",
}


def render(table: Table, fmt: str) -> bytes:
    """The Table as an xlsx, PDF or CSV file."""
    if fmt == "csv":
        return _csv(table)
    if fmt == "xlsx":
        return _xlsx(table)
    if fmt == "pdf":
        return _pdf(table)
    raise ValueError(f"Unknown report format: {fmt}")


def _frame(table: Table) -> pd.DataFrame:
    return pd.DataFrame(table.rows, columns=list(table.columns), dtype=object)


def _csv(table: Table) -> bytes:
    # utf-8-sig: Excel on Windows reads the file as UTF-8 only when it starts with a byte-order mark.
    return _frame(table).to_csv(index=False).encode("utf-8-sig")


def _xlsx(table: Table) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        _frame(table).to_excel(writer, index=False, sheet_name="Report")
        sheet = writer.sheets["Report"]
        for column in sheet.columns:  # wide enough for the longest value
            sheet.column_dimensions[column[0].column_letter].width = max(len(str(c.value or "")) for c in column) + 2
    return buffer.getvalue()


def _pdf(table: Table) -> bytes:
    buffer = io.BytesIO()
    styles = getSampleStyleSheet()
    document = SimpleDocTemplate(buffer, pagesize=landscape(A4), title=table.title,
                                 leftMargin=12 * mm, rightMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm)
    cells = [list(table.columns)] + [["" if value is None else str(value) for value in row] for row in table.rows]
    grid = PdfTable(cells, repeatRows=1)  # the header repeats on every page
    grid.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9ecef")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
    ]))
    story = [Paragraph(table.title, styles["Title"])]
    if table.note:
        story.append(Paragraph(table.note, styles["Normal"]))
    story += [Spacer(1, 4 * mm), grid]
    if not table.rows:
        story.append(Paragraph("No rows.", styles["Normal"]))
    document.build(story)
    return buffer.getvalue()
