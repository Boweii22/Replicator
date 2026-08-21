from __future__ import annotations

import os

from packages.schemas.models import VisionAssessment

RUBRIC = """Compare the paper figure with the reproduced figure as scientific evidence.
Judge trend, ordering of series, axis scale comparability, and whether the scientific conclusion is
the same. Cite visible details such as labels, extrema, crossings, and relative gaps. Do not infer
missing values and do not treat stylistic similarity as scientific reproduction.
"""


class GeminiVisionAssessor:
    def __init__(self) -> None:
        from google import genai
        self.model = os.getenv("MODEL_ID", "gemini-3.5-flash")
        self.client = genai.Client(vertexai=True, project=os.environ["GOOGLE_CLOUD_PROJECT"],
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "global"))

    async def compare(self, paper_png: bytes, reproduced_png: bytes) -> VisionAssessment:
        from google.genai import types
        response = await self.client.aio.models.generate_content(model=self.model,
            contents=[RUBRIC, types.Part.from_bytes(data=paper_png, mime_type="image/png"),
                "REPRODUCED FIGURE:", types.Part.from_bytes(data=reproduced_png, mime_type="image/png")],
            config=types.GenerateContentConfig(temperature=0.1,
                response_mime_type="application/json", response_schema=VisionAssessment))
        if response.parsed is None:
            raise ValueError("Gemini returned no structured visual assessment")
        return VisionAssessment.model_validate(response.parsed)
