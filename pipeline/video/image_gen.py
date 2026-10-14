"""
image_gen.py — Local still generation for shots with no good stock match
=========================================================================
SDXL-Lightning (ByteDance, 4-step UNet on SDXL base) in fp16 fits the RTX 3080's
10 GB and makes a 768×1344 portrait frame in a few seconds. The renderer adds
Ken Burns motion so a still reads as a shot.

make_placeholder() is the last resort (no GPU / model download failed): a
gradient card with the shot query, so the pipeline always finishes and the
evaluator's CLIP score shows the shot was weak.

Config (.env, optional):
  VIDEO_IMAGE_GEN = sdxl_lightning | off
  SDXL_BASE       = stabilityai/stable-diffusion-xl-base-1.0
"""

from __future__ import annotations

import hashlib
import os
import textwrap
from pathlib import Path

LIGHTNING_REPO = "ByteDance/SDXL-Lightning"
LIGHTNING_UNET = "sdxl_lightning_4step_unet.safetensors"
IMAGE_SIZE = (768, 1344)   # SDXL portrait bucket, close to 9:16


class ImageGenError(RuntimeError):
    pass


def image_gen_enabled() -> bool:
    return os.getenv("VIDEO_IMAGE_GEN", "sdxl_lightning").lower() not in ("off", "none", "0", "false")


class SDXLLightning:
    """Lazy-loaded SDXL-Lightning text-to-image pipeline."""

    def __init__(self, base: str | None = None):
        self.base = base or os.getenv("SDXL_BASE", "stabilityai/stable-diffusion-xl-base-1.0")
        self._pipe = None

    def _load(self):
        if self._pipe is not None:
            return self._pipe
        try:
            import torch
            from diffusers import EulerDiscreteScheduler, StableDiffusionXLPipeline, UNet2DConditionModel
            from huggingface_hub import hf_hub_download
            from safetensors.torch import load_file
        except ImportError as e:
            raise ImageGenError("diffusers/torch not installed") from e
        if not torch.cuda.is_available():
            raise ImageGenError("SDXL-Lightning needs a CUDA GPU")

        # Built on CPU, then model-CPU-offload streams one component at a time
        # onto the GPU: peak VRAM ≈ the UNet, which fits a 10 GB card next to
        # Kokoro and CLIP.
        unet_config = UNet2DConditionModel.load_config(self.base, subfolder="unet")
        unet = UNet2DConditionModel.from_config(unet_config).to(torch.float16)
        unet.load_state_dict(load_file(hf_hub_download(LIGHTNING_REPO, LIGHTNING_UNET), device="cpu"))
        pipe = StableDiffusionXLPipeline.from_pretrained(
            self.base, unet=unet, torch_dtype=torch.float16, variant="fp16")
        pipe.enable_model_cpu_offload()
        pipe.vae.enable_tiling()
        pipe.scheduler = EulerDiscreteScheduler.from_config(
            pipe.scheduler.config, timestep_spacing="trailing")
        pipe.set_progress_bar_config(disable=True)
        self._pipe = pipe
        return pipe

    def generate(self, prompt: str, out_path: str | Path, seed: int | None = None) -> Path:
        import torch

        pipe = self._load()
        seed = seed if seed is not None else int(hashlib.sha1(prompt.encode()).hexdigest()[:8], 16)
        # guidance_scale=0 (Lightning is distilled without CFG), so negative prompts have no effect
        image = pipe(prompt, num_inference_steps=4, guidance_scale=0,
                     width=IMAGE_SIZE[0], height=IMAGE_SIZE[1],
                     generator=torch.Generator("cpu").manual_seed(seed)).images[0]
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(out_path)
        return out_path

    def unload(self):
        """Free VRAM once all shots are generated."""
        if self._pipe is None:
            return
        import torch

        self._pipe = None
        torch.cuda.empty_cache()


def make_placeholder(text: str, out_path: str | Path, size=(1080, 1920)) -> Path:
    """Gradient card with the shot query — used only when no real visual exists."""
    from PIL import Image, ImageDraw, ImageFont

    digest = hashlib.sha1(text.encode()).digest()
    top = tuple(40 + b % 80 for b in digest[:3])
    bottom = tuple(10 + b % 40 for b in digest[3:6])
    w, h = size
    img = Image.new("RGB", size)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / (h - 1)
        draw.line([(0, y), (w, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))

    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 64)
    except OSError:
        font = ImageFont.load_default()
    lines = textwrap.wrap(text.upper(), width=18)[:5]
    y = h // 2 - len(lines) * 45
    for line in lines:
        width = draw.textlength(line, font=font)
        draw.text(((w - width) / 2, y), line, font=font, fill=(235, 235, 235))
        y += 90

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path
