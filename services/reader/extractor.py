from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from packages.schemas.models import PaperExtraction, ReaderResult
from services.reader.agent import INSTRUCTION, MODEL
from services.reader.security import delimit_untrusted


class ClaimsExtractor(Protocol):
    async def extract(self, paper: PaperExtraction) -> ReaderResult: ...


class VertexClaimsExtractor:
    """Structured-output utility used by the ADK reader's ingestion tool."""

    def __init__(self) -> None:
        from google import genai

        project = os.environ["GOOGLE_CLOUD_PROJECT"]
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
        self.client = genai.Client(vertexai=True, project=project, location=location)

    async def extract(self, paper: PaperExtraction) -> ReaderResult:
        from google.genai import types

        prompt = (
            f"{INSTRUCTION}\n\n"
            f"The parser observed {paper.page_count} pages and {len(paper.figure_paths)} images.\n"
            + delimit_untrusted(paper.full_text)
        )
        contents = [prompt]
        for path in paper.figure_paths[:12]:
            if path.startswith(("gs://", "file://")):
                continue
            try:
                image = Path(path).read_bytes()
            except OSError:
                continue
            mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
            contents.append(types.Part.from_bytes(data=image, mime_type=mime))
        response = await self.client.aio.models.generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=ReaderResult,
            ),
        )
        if response.parsed is None:
            raise ValueError("Gemini returned no structured claim extraction")
        return ReaderResult.model_validate(response.parsed)
