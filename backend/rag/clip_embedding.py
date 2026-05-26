from __future__ import annotations

"""CLIP embedding for images (and text queries against image collection).

Uses openai/clip-vit-base-patch32 via HuggingFace Transformers.
Output dimension: 512, L2-normalised float32.

Install: pip install transformers torch torchvision pillow
"""

import base64
import io
from functools import lru_cache

import numpy as np

CLIP_MODEL = "openai/clip-vit-base-patch32"
CLIP_DIM = 512


@lru_cache(maxsize=1)
def _get_clip():
    from transformers import CLIPModel, CLIPProcessor
    model = CLIPModel.from_pretrained(CLIP_MODEL)
    processor = CLIPProcessor.from_pretrained(CLIP_MODEL)
    model.eval()
    return model, processor


def _normalise(vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec


def embed_image_b64(data_b64: str) -> np.ndarray:
    """Embed a base64-encoded PNG/JPEG image → 512-dim unit vector."""
    from PIL import Image

    model, processor = _get_clip()
    img = Image.open(io.BytesIO(base64.b64decode(data_b64))).convert("RGB")
    inputs = processor(images=img, return_tensors="pt")

    import torch
    with torch.no_grad():
        features = model.get_image_features(**inputs)

    vec = features[0].cpu().numpy().astype("float32")
    return _normalise(vec)


def embed_image_query(text: str) -> np.ndarray:
    """Encode text via CLIP text encoder for querying the image collection."""
    model, processor = _get_clip()
    inputs = processor(text=[text], return_tensors="pt", padding=True)

    import torch
    with torch.no_grad():
        features = model.get_text_features(**inputs)

    vec = features[0].cpu().numpy().astype("float32")
    return _normalise(vec)


def preload() -> None:
    """Call at server startup to warm up model (downloads ~340 MB on first run)."""
    _get_clip()
