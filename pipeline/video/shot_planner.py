"""
shot_planner.py — Scene → sub-shots with visual search queries
================================================================
A scene of 5 s for a creator who cuts every 1.84 s becomes 3 shots. Each shot
needs its own concrete, filmable query ("woman running at sunrise"), because
`clip_idea` is usually a long, abstract paragraph that stock search and
image models handle badly.

The local LLM (pipeline/local_llm.py) writes N queries per scene in one call.
If the LLM is unavailable the keyword fallback still yields usable queries,
so video generation never depends on Ollama being up.
"""

from __future__ import annotations

import re

STOPWORDS = set("""
a an the and or but of to in on at for with from by as is are was were be been being this that these
those it its into over under while then than so very just also can will would should could about
some any each every all more most other such only own same too up down out off again further once
here there when where why how what which who whom both few no nor not now camera shot shots clip
clips footage scene video showing shows show cut cuts quick fast slow montage b-roll broll overlay
text caption captions frame frames visual visuals screen talking head close-up closeup medium wide
""".split())

SHOT_VARIATIONS = ["", "close up", "cinematic", "detail", "silhouette", "slow motion"]
# No "no text": with CFG off, naming text in the prompt makes SDXL draw letters
IMAGE_STYLE = "photorealistic, cinematic lighting, vertical 9:16 composition, high detail, plain unbranded surfaces"


def keywords(text: str, limit: int = 5) -> list[str]:
    """Content words of `text` in order, de-duplicated, stopwords removed."""
    text = re.sub(r"^\s*(b-?roll|screen|visual)\s*:\s*", "", text, flags=re.I)
    seen, out = set(), []
    for word in re.findall(r"[A-Za-z][A-Za-z'-]+", text.lower()):
        if word in STOPWORDS or len(word) < 3 or word in seen:
            continue
        seen.add(word)
        out.append(word)
        if len(out) == limit:
            break
    return out


def fallback_queries(clip_idea: str, voiceover: str, n: int) -> list[str]:
    """Keyword queries, one per shot, varied so shots don't repeat."""
    words = keywords(clip_idea, 8) or keywords(voiceover, 8) or ["abstract", "background"]
    queries = []
    for i in range(n):
        # Slide a 3-word window over the keywords, then vary the framing
        window = words[i % max(1, len(words) - 2):][:3] or words[:3]
        variation = SHOT_VARIATIONS[i % len(SHOT_VARIATIONS)]
        queries.append(" ".join(window + ([variation] if variation else [])))
    return queries


def llm_queries(clip_idea: str, voiceover: str, n: int, niche: str = "") -> list[str]:
    """Ask the local LLM for `n` short stock-footage queries. Raises on failure."""
    from pipeline.local_llm import chat_json

    prompt = (
        f"A short vertical video scene needs {n} consecutive B-roll shots.\n"
        f"Niche: {niche or 'general'}\n"
        f"Scene visual idea: {clip_idea}\n"
        f"Voiceover during the scene: {voiceover}\n\n"
        f"Write exactly {n} stock-footage search queries, one per shot, in order.\n"
        "Rules: 2-5 words each; concrete, filmable things (people, objects, places, actions);\n"
        "no abstract words, no text/graphics, no camera jargon; shots must differ from each other.\n"
        'Return JSON: {"queries": ["...", "..."]}'
    )
    result = chat_json(prompt, system="You are a video editor choosing stock footage.",
                       temperature=0.4, max_tokens=200)
    queries = [q.strip() for q in result.get("queries", []) if isinstance(q, str) and q.strip()]
    if len(queries) < n:
        raise ValueError(f"LLM returned {len(queries)} queries, needed {n}")
    return [" ".join(q.split()[:6]) for q in queries[:n]]


def plan_queries(clip_idea: str, voiceover: str, n: int, niche: str = "",
                 use_llm: bool = True) -> tuple[list[str], str]:
    """Return (queries, source) where source is 'llm' or 'keywords'."""
    if use_llm:
        try:
            return llm_queries(clip_idea, voiceover, n, niche), "llm"
        except Exception as e:
            print(f"[ShotPlanner] LLM queries unavailable ({e}); using keyword fallback")
    return fallback_queries(clip_idea, voiceover, n), "keywords"


def image_prompt(query: str, clip_idea: str, look: list[str] | None = None) -> str:
    """
    Prompt for the image model: shot query first, scene context, then the
    creator's look words (personalised only), then the fixed quality suffix.
    """
    parts = [query, " ".join(keywords(clip_idea, 6)), ", ".join(look or []), IMAGE_STYLE]
    return ", ".join(p for p in parts if p)
