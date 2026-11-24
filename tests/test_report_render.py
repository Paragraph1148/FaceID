"""F6.2: every report downloads as xlsx, PDF and CSV with the same rows (faceid.reports.render)."""

import base64
import csv
import io
import re
import zlib

import openpyxl
import pytest

from faceid.reports.render import FORMATS, render
from faceid.reports.tables import Table

TABLE = Table(
    "Subject-wise report: CA261481 Machine Learning",
    ("Enrolment Number", "Name", "Held", "Attendance Percentage", "Minutes Late"),
    [("SSPU20260001", "Asha Verma", 4, 68.8, None), ("SSPU20260002", "Ravi Kumar", 4, 100.0, 12)],
    "Counts closed Class Sessions only.",
)


def pdf_text(data: bytes) -> str:
    """The text drawn in a PDF. ReportLab writes each string as (text) Tj, in ASCII85 + Flate encoded streams."""
    chunks = [zlib.decompress(base64.a85decode(stream.strip(), adobe=False))
              for stream in re.findall(rb"/ASCII85Decode /FlateDecode \] /Length \d+\s*>>\s*stream\r?\n(.*?)~>", data, re.S)]
    return b" ".join(re.findall(rb"\((.*?)\) Tj", b"\n".join(chunks))).decode("latin-1")


def test_csv_has_a_header_and_the_rows():
    data = render(TABLE, "csv")

    rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))
    assert rows == [list(TABLE.columns), ["SSPU20260001", "Asha Verma", "4", "68.8", ""],
                    ["SSPU20260002", "Ravi Kumar", "4", "100.0", "12"]]


def test_xlsx_has_a_header_and_the_rows_as_numbers():
    data = render(TABLE, "xlsx")

    sheet = openpyxl.load_workbook(io.BytesIO(data)).active
    assert list(sheet.iter_rows(values_only=True)) == [TABLE.columns, *TABLE.rows]


def test_pdf_has_the_title_note_header_and_rows():
    data = render(TABLE, "pdf")

    assert data.startswith(b"%PDF")
    text = pdf_text(data)
    for expected in (TABLE.title, TABLE.note, "Enrolment Number", "SSPU20260001", "Asha Verma", "68.8", "Ravi Kumar"):
        assert expected in text


def test_an_empty_report_still_renders_its_header():
    empty = Table("Defaulter list", ("Enrolment Number", "Name"), [])

    for fmt in FORMATS:
        assert render(empty, fmt)
    assert render(empty, "csv").decode("utf-8-sig").strip() == "Enrolment Number,Name"


def test_an_unknown_format_is_refused():
    with pytest.raises(ValueError):
        render(TABLE, "docx")
