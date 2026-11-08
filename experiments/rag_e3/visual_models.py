"""
visual_models.py — The asset-search methods compared in E3
===========================================================
Every method does the same job: given scene descriptions (queries) and the
creator's photos (assets), return scores[q, a] — higher means photo a fits
scene q better.

Route A — compare text and image directly (shared image–text embedding space)
  clip-b32      OpenAI CLIP ViT-B/32 — what the project uses now (module2, evaluator)
  clip-l14      OpenAI CLIP ViT-L/14 — bigger CLIP
  siglip-base   Google SigLIP base   — newer, usually stronger at retrieval
  siglip2-base  Google SigLIP 2 base — 2025 successor, multilingual training data
  mclip         Multilingual CLIP (text encoder distilled for 50+ languages)

Route B — describe each photo in words, then search the words
  caption       BLIP-large writes a caption per photo; a text-embedding model
                (bge-small, from E1) matches scenes against the captions

Route C — hybrid: two routes merged with Reciprocal Rank Fusion ('a+b')
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

RRF_K = 60
BGE_QUERY = "Represent this sentence for searching relevant passages: "


def _device() -> str:
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


def _params_m(model) -> float:
    return round(sum(p.numel() for p in model.parameters()) / 1e6, 1)


def _embeddings(output) -> np.ndarray:
    """
    get_image_features / get_text_features → numpy. transformers 4.x returns the
    embedding tensor; 5.x returns a model output with it in `pooler_output`
    (already projected for CLIP; SigLIP's pooled head output).
    """
    tensor = output if hasattr(output, "cpu") else output.pooler_output
    return tensor.detach().cpu().numpy()


def _normalize(x: np.ndarray) -> np.ndarray:
    return x / np.clip(np.linalg.norm(x, axis=-1, keepdims=True), 1e-9, None)


class AssetRetriever:
    name: str = "base"
    route: str = ""
    params_m: float | None = None
    # Whether scores are cosine similarities that a fallback threshold can use.
    # RRF scores are rank-based, so hybrids cannot be thresholded.
    thresholdable: bool = True

    def index(self, images: list, paths: list[Path]) -> None:
        raise NotImplementedError

    def score(self, queries: list[str]) -> np.ndarray:
        raise NotImplementedError


class HFImageText(AssetRetriever):
    """CLIP / SigLIP through Hugging Face transformers."""

    route = "A: image–text embedding"

    def __init__(self, name: str, model_id: str, text_padding: str | bool = True):
        self.name = name
        self.model_id = model_id
        # SigLIP was trained with text padded to max_length; padding differently hurts it.
        self.text_padding = text_padding
        self._model = None

    def _load(self):
        if self._model is None:
            from transformers import AutoModel, AutoProcessor
            self._processor = AutoProcessor.from_pretrained(self.model_id)
            self._model = AutoModel.from_pretrained(self.model_id).to(_device()).eval()
            self.params_m = _params_m(self._model)
        return self._model

    def index(self, images: list, paths: list[Path]) -> None:
        import torch
        model = self._load()
        vecs = []
        for start in range(0, len(images), 8):
            batch = self._processor(images=images[start:start + 8], return_tensors="pt").to(model.device)
            with torch.no_grad():
                vecs.append(_embeddings(model.get_image_features(**batch)))
        self._image_vecs = _normalize(np.concatenate(vecs))

    def score(self, queries: list[str]) -> np.ndarray:
        import torch
        model = self._load()
        batch = self._processor(text=queries, padding=self.text_padding, truncation=True,
                                return_tensors="pt").to(model.device)
        with torch.no_grad():
            text = _embeddings(model.get_text_features(**batch))
        return _normalize(text) @ self._image_vecs.T


class MultilingualCLIP(AssetRetriever):
    """CLIP ViT-B/32 image encoder + a multilingual text encoder trained to match it."""

    route = "A: image–text embedding"

    def __init__(self, name: str = "mclip"):
        self.name = name
        self._models = None

    def _load(self):
        if self._models is None:
            from sentence_transformers import SentenceTransformer
            image_model = SentenceTransformer("sentence-transformers/clip-ViT-B-32", device=_device())
            text_model = SentenceTransformer("sentence-transformers/clip-ViT-B-32-multilingual-v1", device=_device())
            self._models = (image_model, text_model)
            self.params_m = _params_m(image_model) + _params_m(text_model)
        return self._models

    def index(self, images: list, paths: list[Path]) -> None:
        image_model, _ = self._load()
        self._image_vecs = np.asarray(image_model.encode(images, batch_size=8, normalize_embeddings=True,
                                                         show_progress_bar=False))

    def score(self, queries: list[str]) -> np.ndarray:
        _, text_model = self._load()
        return np.asarray(text_model.encode(queries, normalize_embeddings=True,
                                            show_progress_bar=False)) @ self._image_vecs.T


class CaptionThenText(AssetRetriever):
    """
    Route B: caption every photo with BLIP, then text-search the captions.
    Captions are cached in the library folder (captions_blip.json) — they are
    also what the Scripting Agent could use to write about this campus.
    """

    route = "B: caption → text search"
    CAPTION_MODEL = "Salesforce/blip-image-captioning-large"
    TEXT_MODEL = "BAAI/bge-small-en-v1.5"

    def __init__(self, name: str = "caption"):
        self.name = name
        self._text_model = None
        self.captions: dict[str, str] = {}

    def _caption(self, images: list, paths: list[Path]) -> list[str]:
        cache_path = paths[0].parent.parent / "captions_blip.json" if paths else None
        cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path and cache_path.exists() else {}
        keys = [f"{p.parent.name}/{p.name}" for p in paths]   # assets/ and distractors/ may reuse names
        missing = [i for i, k in enumerate(keys) if k not in cache]
        if missing:
            import torch
            from transformers import BlipForConditionalGeneration, BlipProcessor
            print(f"    [caption] BLIP captioning {len(missing)} photos (cached afterwards)...", flush=True)
            processor = BlipProcessor.from_pretrained(self.CAPTION_MODEL)
            model = BlipForConditionalGeneration.from_pretrained(self.CAPTION_MODEL).to(_device()).eval()
            for i in missing:
                inputs = processor(images=images[i], return_tensors="pt").to(model.device)
                with torch.no_grad():
                    out = model.generate(**inputs, max_new_tokens=40, num_beams=3)
                cache[keys[i]] = processor.decode(out[0], skip_special_tokens=True).strip()
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        self.captions = {k: cache[k] for k in keys}
        return [cache[k] for k in keys]

    def _encoder(self):
        if self._text_model is None:
            from sentence_transformers import SentenceTransformer
            self._text_model = SentenceTransformer(self.TEXT_MODEL, device=_device())
            # BLIP-large (~470M) + bge-small (~33M), reported as the route's total size.
            self.params_m = 470.0 + _params_m(self._text_model)
        return self._text_model

    def index(self, images: list, paths: list[Path]) -> None:
        captions = self._caption(images, paths)
        self._caption_vecs = np.asarray(self._encoder().encode(captions, normalize_embeddings=True,
                                                               show_progress_bar=False))

    def score(self, queries: list[str]) -> np.ndarray:
        return np.asarray(self._encoder().encode([BGE_QUERY + q for q in queries], normalize_embeddings=True,
                                                 show_progress_bar=False)) @ self._caption_vecs.T


class Hybrid(AssetRetriever):
    """Reciprocal Rank Fusion of two methods: score = Σ 1 / (k + rank)."""

    route = "C: hybrid (RRF)"
    thresholdable = False

    def __init__(self, name: str, first: AssetRetriever, second: AssetRetriever):
        self.name = name
        self.parts = (first, second)

    def index(self, images: list, paths: list[Path]) -> None:
        for part in self.parts:
            part.index(images, paths)
        self.params_m = round(sum(p.params_m or 0 for p in self.parts), 1) or None

    def score(self, queries: list[str]) -> np.ndarray:
        return sum(1.0 / (RRF_K + tie_aware_ranks(part.score(queries))) for part in self.parts)


def tie_aware_ranks(scores: np.ndarray) -> np.ndarray:
    """rank[q, a] = number of assets scoring >= asset a (rank 1 = best; ties share the worst rank)."""
    return (scores[:, None, :] >= scores[:, :, None]).sum(axis=-1)


# ─── Registry ──────────────────────────────────────────────────────────────────

METHODS = {
    "clip-b32":     lambda: HFImageText("clip-b32", "openai/clip-vit-base-patch32"),
    "clip-l14":     lambda: HFImageText("clip-l14", "openai/clip-vit-large-patch14"),
    "siglip-base":  lambda: HFImageText("siglip-base", "google/siglip-base-patch16-224", text_padding="max_length"),
    "siglip2-base": lambda: HFImageText("siglip2-base", "google/siglip2-base-patch16-224", text_padding="max_length"),
    "mclip":        lambda: MultilingualCLIP(),
    "caption":      lambda: CaptionThenText(),
}

DEFAULT_METHODS = list(METHODS) + ["siglip-base+caption", "clip-b32+caption"]
QUICK_METHODS = ["clip-b32", "siglip-base", "caption", "siglip-base+caption"]


def make_retriever(name: str) -> AssetRetriever:
    if "+" in name:
        first, second = name.split("+", 1)
        return Hybrid(name, make_retriever(first), make_retriever(second))
    if name not in METHODS:
        raise ValueError(f"Unknown method '{name}'. Known: {', '.join(METHODS)} (or 'a+b' for a hybrid)")
    return METHODS[name]()
