"""
Tests for creator-supplied photo matching (experiment E3 → SigLIP + threshold).
A fake encoder stands in for SigLIP, so no model is downloaded.
"""

from pathlib import Path

import numpy as np
import pytest

from pipeline.video.assets import AssetResolver
from pipeline.video.creator_assets import (
    DEFAULT_THRESHOLD, CreatorAssetLibrary, asset_id, load_creator_assets,
)


class FakeEncoder:
    """Photo i is the unit vector e_i; a scene's vector is set per test."""

    def __init__(self, scene_vectors: dict[str, list[float]]):
        self.scene_vectors = scene_vectors
        self.image_calls = 0

    def image_embeddings(self, paths):
        self.image_calls += 1
        index = {"cafe.jpg": 0, "lab.png": 1, "hall.jpeg": 2}
        out = np.zeros((len(paths), 3), dtype=np.float32)
        for row, p in enumerate(paths):
            out[row, index[Path(p).name]] = 1.0
        return out

    def text_embeddings(self, texts):
        return np.array([self.scene_vectors[t] for t in texts], dtype=np.float32)


@pytest.fixture
def photos(tmp_path):
    folder = tmp_path / "photos"
    folder.mkdir()
    for name in ("cafe.jpg", "lab.png", "hall.jpeg", "notes.txt"):
        (folder / name).write_bytes(b"x")
    return folder


SCENES = {
    "A busy cafeteria": [0.30, 0.05, 0.02],
    "A graduation ceremony": [0.03, 0.02, 0.05],   # nothing above threshold
}


def test_library_lists_only_images(photos):
    lib = CreatorAssetLibrary(photos, encoder=FakeEncoder(SCENES))
    assert sorted(p.name for p in lib.paths) == ["cafe.jpg", "hall.jpeg", "lab.png"]
    assert lib.threshold == DEFAULT_THRESHOLD


def test_match_uses_best_photo_above_threshold(photos):
    lib = CreatorAssetLibrary(photos, encoder=FakeEncoder(SCENES))
    path, score = lib.match("A busy cafeteria")
    assert path.name == "cafe.jpg" and score == pytest.approx(0.30)


def test_match_falls_back_when_nothing_fits(photos):
    lib = CreatorAssetLibrary(photos, encoder=FakeEncoder(SCENES))
    assert lib.match("A graduation ceremony") is None


def test_match_skips_used_photos_but_respects_threshold(photos):
    lib = CreatorAssetLibrary(photos, encoder=FakeEncoder(SCENES), threshold=0.04)
    used = {asset_id(photos / "cafe.jpg")}
    path, _ = lib.match("A busy cafeteria", used)
    assert path.name == "lab.png"                         # 0.05 ≥ 0.04
    used.add(asset_id(path))
    assert lib.match("A busy cafeteria", used) is None    # hall 0.02 < 0.04


def test_threshold_from_env(photos, monkeypatch):
    monkeypatch.setenv("CREATOR_ASSET_THRESHOLD", "0.5")
    assert CreatorAssetLibrary(photos, encoder=FakeEncoder(SCENES)).threshold == 0.5


def test_embeddings_cached_on_disk(photos, tmp_path):
    enc = FakeEncoder(SCENES)
    CreatorAssetLibrary(photos, cache_dir=tmp_path / "cache", encoder=enc).rank("A busy cafeteria")
    CreatorAssetLibrary(photos, cache_dir=tmp_path / "cache", encoder=enc).rank("A busy cafeteria")
    assert enc.image_calls == 1


def test_load_creator_assets_none_without_photos(tmp_path, monkeypatch):
    monkeypatch.delenv("CREATOR_ASSETS_DIR", raising=False)
    assert load_creator_assets(None) is None
    assert load_creator_assets(tmp_path) is None


def test_resolver_prefers_creator_photo_then_falls_back(photos, tmp_path):
    lib = CreatorAssetLibrary(photos, encoder=FakeEncoder(SCENES))
    resolver = AssetResolver(tmp_path / "cache", pexels_key="", use_image_gen=False)
    used: set = set()

    asset = resolver.resolve("cafeteria", used_ids=used, creator_assets=lib, scene="A busy cafeteria")
    assert asset.source == "creator" and Path(asset.path).name == "cafe.jpg"
    assert asset.kind == "image" and asset.asset_score == pytest.approx(0.30)

    asset = resolver.resolve("graduation", used_ids=used, creator_assets=lib, scene="A graduation ceremony")
    assert asset.source == "placeholder"


def test_resolver_without_library_unchanged(tmp_path):
    resolver = AssetResolver(tmp_path / "cache", pexels_key="", use_image_gen=False)
    assert resolver.resolve("anything").source == "placeholder"


def test_suggest_gives_each_photo_to_one_scene(photos):
    scenes = {"cafe one": [0.30, 0.0, 0.0], "cafe two": [0.20, 0.10, 0.0], "nothing": [0.01, 0.0, 0.0]}
    lib = CreatorAssetLibrary(photos, encoder=FakeEncoder(scenes))
    out = lib.suggest(list(scenes))
    assert [s["suggested"] for s in out] == ["cafe.jpg", "lab.png", None]
    assert out[0]["ranked"][0] == {"name": "cafe.jpg", "score": pytest.approx(0.30)}


def test_confirmed_photo_used_even_below_threshold(photos, tmp_path):
    lib = CreatorAssetLibrary(photos, encoder=FakeEncoder(SCENES))
    asset = AssetResolver.creator_photo(lib, "hall.jpeg", "A graduation ceremony", "graduation")
    assert asset.source == "creator" and asset.asset_score == pytest.approx(0.05)
    with pytest.raises(ValueError):
        AssetResolver.creator_photo(lib, "missing.jpg", "x", "x")


@pytest.mark.skipif(not __import__("pipeline.video.renderer", fromlist=["x"]).ffmpeg_available(),
                    reason="ffmpeg not installed")
def test_generate_video_uses_reviewed_choices(tmp_path, sample_production_plan):
    from PIL import Image

    from pipeline.agents.video_agent import generate_video
    from tests.backend.test_video_render import FakeTTS

    folder = tmp_path / "photos"
    folder.mkdir()
    for name, colour in (("cafe.jpg", "red"), ("lab.png", "blue"), ("hall.jpeg", "green")):
        Image.new("RGB", (64, 64), colour).save(folder / name)
    plan = {**sample_production_plan, "scenes": sample_production_plan["scenes"][:2]}
    lib = CreatorAssetLibrary(folder, encoder=FakeEncoder({sc.get("visual") or sc.get("clip_idea"): [0.3, 0.0, 0.0]
                                                           for sc in plan["scenes"]}))
    result = generate_video(plan, {}, out_dir=tmp_path / "out", tts=FakeTTS(0.3),
                            resolver=AssetResolver(tmp_path / "cache", pexels_key="", use_image_gen=False),
                            use_llm=False, run_evaluation=False, creator=None,
                            assets=lib, scene_assets={0: "hall.jpeg", 1: None})
    first, second = result["timeline"].scenes
    assert first.shots[0].asset.source == "creator" and first.shots[0].asset.source_id == "hall.jpeg"
    assert all(sh.asset.source != "creator" for sh in first.shots[1:] + second.shots)   # creator said no
