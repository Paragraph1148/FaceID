"""Writing a report Table as a file (F6.2): xlsx and CSV through Pandas, PDF through ReportLab.

All three are written from the same Table, so they contain the same rows by construction.
"""

import io
from collections.abc import Callable
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from reportlab.platypus import Table as PdfTable
from reportlab.platypus import TableStyle

from faceid.reports.tables import Table

FORMULA_STARTS = ("=", "+", "-", "@")  # a spreadsheet runs text starting with these as a formula


def _frame(rows: list[tuple], table: Table) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=list(table.columns), dtype=object)


def _as_text(value: object) -> object:
    """A leading apostrophe makes a spreadsheet show text as typed instead of running it as a formula."""
    return "'" + value if isinstance(value, str) and value.startswith(FORMULA_STARTS) else value


def _csv(table: Table) -> bytes:
    rows = [tuple(_as_text(value) for value in row) for row in table.rows]
    # utf-8-sig: Excel on Windows reads the file as UTF-8 only when it starts with a byte-order mark.
    return _frame(rows, table).to_csv(index=False).encode("utf-8-sig")


def _xlsx(table: Table) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        _frame(table.rows, table).to_excel(writer, index=False, sheet_name="Report")
        sheet = writer.sheets["Report"]
        for row in sheet.iter_rows():
            for cell in row:
                if cell.data_type == "f":  # openpyxl turns text starting with "=" into a formula; keep it text
                    cell.data_type = "s"
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
    # Paragraph reads its text as markup, so names are escaped: "A <b>" must print as typed.
    story = [Paragraph(escape(table.title), styles["Title"])]
    if table.note:
        story.append(Paragraph(escape(table.note), styles["Normal"]))
    story += [Spacer(1, 4 * mm), grid]
    if not table.rows:
        story.append(Paragraph("No rows.", styles["Normal"]))
    document.build(story)
    return buffer.getvalue()


# Each format's media type and writer. The web pages, the download links and `render` all read this one map.
FORMATS: dict[str, tuple[str, Callable[[Table], bytes]]] = {
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", _xlsx),
    "pdf": ("application/pdf", _pdf),
    "csv": ("text/csv", _csv),
}


def media_type(fmt: str) -> str:
    return FORMATS[fmt][0]


def render(table: Table, fmt: str) -> bytes:
    """The Table as an xlsx, PDF or CSV file."""
    if fmt not in FORMATS:
        raise ValueError(f"Unknown report format: {fmt}")
    return FORMATS[fmt][1](table)
