import io

import numpy as np
from PIL import Image, ImageOps


def figure_similarity(paper_bytes: bytes, reproduced_bytes: bytes) -> float:
    paper = _normalized(paper_bytes)
    reproduced = _normalized(reproduced_bytes)
    mse = float(np.mean((paper.astype(np.float32) - reproduced.astype(np.float32)) ** 2))
    return round(max(0.0, min(1.0, 1.0 - mse / (255.0**2))), 4)


def _normalized(payload: bytes) -> np.ndarray:
    try:
        image = Image.open(io.BytesIO(payload)).convert("L")
    except Exception as exc:
        raise ValueError("Figure artifact is not a readable image") from exc
    return np.asarray(ImageOps.fit(image, (512, 512), method=Image.Resampling.LANCZOS))
