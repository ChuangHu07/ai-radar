from io import BytesIO
from pypdf import PdfReader, PdfWriter
from ..errors import AppError

MAX_BYTES = 50 * 1024 * 1024
MAX_PAGES = 150


def inspect_pdf(data: bytes) -> dict:
    if len(data) > MAX_BYTES:
        raise AppError("PDF_TOO_LARGE", "每篇 PDF 最大 50 MiB。", 413)
    if not data.lstrip()[:1024].startswith(b"%PDF-"):
        raise AppError("PDF_UNREADABLE", "文件不是有效的 PDF。")
    try:
        reader = PdfReader(BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise AppError("PDF_ENCRYPTED", "文件已加密，请上传未加密的 PDF。")
        if not 1 <= len(reader.pages) <= MAX_PAGES:
            raise AppError("PDF_PAGE_LIMIT", "每篇 PDF 需要包含 1–150 页。")
        texts = [(page.extract_text() or "").strip() for page in reader.pages]
        if not any(texts):
            raise AppError("PDF_NO_TEXT", "没有可提取的正文，可能是扫描 PDF。请上传带可解析文字的版本。")
        checks = [{"page": i + 1, "characters": len(text), "has_text": bool(text)} for i, text in enumerate(texts)]
        return {"page_count": len(texts), "page_checks": checks,
                "warnings": [f"第 {i + 1} 页没有可提取文字；图像 / 空白内容仍需模型检查。" for i, text in enumerate(texts) if not text],
                "texts": texts}
    except AppError:
        raise
    except Exception as exc:
        raise AppError("PDF_UNREADABLE", "PDF 已损坏或无法解析，请重新上传。") from exc


def page_parts(data: bytes, start: int = 0, end: int | None = None):
    """All pages, in order. Ranges use zero-based exclusive end internally."""
    reader = PdfReader(BytesIO(data))
    end = len(reader.pages) if end is None else end
    for first in range(start, end, 40):
        last = min(first + 40, end)
        writer = PdfWriter()
        for page in reader.pages[first:last]:
            writer.add_page(page)
        stream = BytesIO()
        writer.write(stream)
        yield first, last, stream.getvalue()
