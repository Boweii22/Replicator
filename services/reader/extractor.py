from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Protocol

from packages.schemas.models import PaperExtraction, ReaderResult
from services.reader.agent import INSTRUCTION, build_agent
from services.reader.security import delimit_untrusted


class ClaimsExtractor(Protocol):
    async def extract(self, paper: PaperExtraction) -> ReaderResult: ...


class VertexClaimsExtractor:
    """Execute the production reader through Google ADK with structured output."""

    async def extract(self, paper: PaperExtraction) -> ReaderResult:
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types

        prompt = (
            f"{INSTRUCTION}\n\n"
            f"The parser observed {paper.page_count} pages and {len(paper.figure_paths)} images.\n"
            + delimit_untrusted(paper.full_text)
        )
        parts = [types.Part.from_text(text=prompt)]
        for index, path in enumerate(paper.figure_paths[:12]):
            if path.startswith(("gs://", "file://")):
                continue
            try:
                image = await asyncio.to_thread(Path(path).read_bytes)
            except OSError:
                continue
            mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
            parts.append(types.Part.from_text(text=f"PAPER IMAGE INDEX {index}:"))
            parts.append(types.Part.from_bytes(data=image, mime_type=mime))

        app_name, user_id = "replicator_reader", "replicator-system"
        sessions = InMemorySessionService()
        session = await sessions.create_session(app_name=app_name, user_id=user_id)
        runner = Runner(app_name=app_name, agent=build_agent(), session_service=sessions)
        final_text = None
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=types.Content(role="user", parts=parts),
        ):
            if event.is_final_response() and event.content:
                final_text = "".join(part.text or "" for part in event.content.parts or [])
        if not final_text:
            raise ValueError("ADK reader returned no structured claim extraction")
        return ReaderResult.model_validate(json.loads(final_text))
