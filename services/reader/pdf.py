from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import httpx

from packages.schemas.models import PaperExtraction
from services.reader.security import scan_untrusted_text

ARXIV_HOSTS = {"arxiv.org", "www.arxiv.org", "export.arxiv.org"}
MAX_PDF_BYTES = 50 * 1024 * 1024


def canonical_pdf_url(source_url: str) -> str:
    parsed = urlparse(source_url)
    if parsed.scheme != "https" or parsed.hostname not in ARXIV_HOSTS:
        raise ValueError("Only HTTPS arXiv URLs are accepted in this phase")
    match = re.fullmatch(r"/(?:abs|pdf)/(\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?", parsed.path)
    if not match:
        raise ValueError("Unsupported arXiv URL format")
    return f"https://arxiv.org/pdf/{match.group(1)}.pdf"


async def fetch_pdf(source_url: str) -> bytes:
    url = canonical_pdf_url(source_url)
    async with httpx.AsyncClient(timeout=45, follow_redirects=True, max_redirects=3) as client:
        response = await client.get(url, headers={"User-Agent": "Replicator/0.1 research-agent"})
        response.raise_for_status()
    final_url = urlparse(str(response.url))
    if final_url.scheme != "https" or final_url.hostname not in ARXIV_HOSTS:
        raise ValueError("arXiv redirected the PDF request to an untrusted host")
    content_type = response.headers.get("content-type", "").lower()
    if "pdf" not in content_type or not response.content.startswith(b"%PDF"):
        raise ValueError("Source did not return a PDF")
    if len(response.content) > MAX_PDF_BYTES:
        raise ValueError("PDF exceeds the 50 MiB ingestion cap")
    return response.content


def extract_pdf(pdf_bytes: bytes, workdir: Path) -> PaperExtraction:
    try:
        import fitz
    except ModuleNotFoundError as exc:
        raise RuntimeError("Install the pymupdf dependency to extract papers") from exc

    workdir.mkdir(parents=True, exist_ok=True)
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    if document.page_count < 1:
        raise ValueError("PDF contains no pages")
    pages = [page.get_text("text") for page in document]
    full_text = "\n\n".join(pages).strip()
    if len(full_text) < 200:
        raise ValueError("PDF has insufficient extractable text")
    first_lines = [line.strip() for line in pages[0].splitlines() if line.strip()]
    title = first_lines[0][:300] if first_lines else "Untitled paper"
    figure_paths: list[str] = []
    for page_index, page in enumerate(document):
        page_target = workdir / f"page-{page_index + 1}.png"
        page_target.write_bytes(
            page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).tobytes("png")
        )
        figure_paths.append(str(page_target))
        for image_index, image in enumerate(page.get_images(full=True)):
            xref = image[0]
            extracted = document.extract_image(xref)
            if not extracted.get("image"):
                continue
            target = workdir / f"page-{page_index + 1}-image-{image_index + 1}.{extracted['ext']}"
            target.write_bytes(extracted["image"])
            figure_paths.append(str(target))
    reasons = scan_untrusted_text(full_text)
    return PaperExtraction(
        title=title,
        full_text=full_text,
        page_count=document.page_count,
        figure_paths=figure_paths,
        injection_suspected=bool(reasons),
        injection_reasons=reasons,
    )
