import pytest
from app.documents.pdf import inspect_pdf, page_parts, MAX_BYTES
from app.errors import AppError
from pdf_factory import pdf_bytes


@pytest.mark.parametrize("data,code", [(b"not a PDF", "PDF_UNREADABLE"), (b"%PDF-broken", "PDF_UNREADABLE"), (b"x" * (MAX_BYTES + 1), "PDF_TOO_LARGE"), (pdf_bytes(encrypted=True), "PDF_ENCRYPTED"), (pdf_bytes(text=False), "PDF_NO_TEXT"), (pdf_bytes(pages=151), "PDF_PAGE_LIMIT")], ids=["wrong-type", "broken", "too-large", "encrypted", "no-text", "too-many-pages"])
def test_file_boundaries(data, code):
    with pytest.raises(AppError) as error:
        inspect_pdf(data)
    assert error.value.code == code


def test_full_page_partitioning():
    data = pdf_bytes(pages=81)
    parsed = inspect_pdf(data)
    assert parsed["page_count"] == 81
    assert all(check["has_text"] for check in parsed["page_checks"])
    parts = list(page_parts(data))
    assert [(a, b) for a, b, _ in parts] == [(0, 40), (40, 80), (80, 81)]
    assert sum(inspect_pdf(chunk)["page_count"] for _, _, chunk in parts) == 81
