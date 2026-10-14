"""
pipeline/video — Module 4: Video Generation
============================================
Script + creator profile → rendered 1080×1920 MP4.

  style_plan.py   creator profile → edit parameters (+ generic baseline)
  tts.py          Kokoro voiceover, speed calibrated to the creator's wpm
  shot_planner.py scene → sub-shots + stock/visual search queries
  assets.py       Pexels + CLIP re-rank → SDXL-Lightning → placeholder
  image_gen.py    SDXL-Lightning (local) and the placeholder card
  timeline.py     typed timeline.json — single source of truth
  renderer.py     FFmpeg render + burned-in ASS captions
  evaluator.py    measured style fidelity of the rendered MP4

The orchestrator is pipeline/agents/video_agent.py.
Heavy libraries (torch, kokoro, diffusers, librosa) are imported lazily so
the pure logic stays importable in CI.
"""
