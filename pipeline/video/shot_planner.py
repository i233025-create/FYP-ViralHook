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

people=False (the default for the Video Agent, VIDEO_ALLOW_PEOPLE=0): SDXL
Lightning runs without CFG, so a negative prompt can't stop it drawing people,
and its people come out with extra limbs and melted faces. Instead people are
kept out of the positive prompt: the LLM is told to pick object/place shots,
and any person, body-part or facial-expression words left in a query or scene
idea are dropped or swapped for the object they stand for
("developer typing" → "laptop with code typing").
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
# Non-photo media the creator look (creator_visual.LOOK_VOCAB["medium"]) can pick
STYLISED_MEDIA = ("3D animated render", "flat 2D illustration", "anime illustration",
                  "screen recording of software")
OBJECT_STYLE = "still life, object-focused composition, empty scene"

# Person words → the object that stands in for them (None = just drop the word)
PEOPLE_WORDS = {
    **dict.fromkeys(["developer", "developers", "programmer", "programmers", "coder", "coders",
                     "engineer", "engineers", "hacker"], "laptop with code"),
    **dict.fromkeys(["user", "users", "customer", "customers"], "smartphone"),
    **dict.fromkeys(["gamer", "gamers"], "game controller"),
    **dict.fromkeys(["athlete", "runner", "trainer", "gymgoer"], "sports equipment"),
    **dict.fromkeys(["chef", "cook"], "kitchen counter"),
    **dict.fromkeys(["student", "students"], "notebook and books"),
    **dict.fromkeys(["me", "i", "my", "myself", "you", "your", "we", "our", "he", "she", "him", "her",
                     "his", "they", "them", "their", "person", "people", "man", "men", "woman", "women",
                     "guy", "guys", "girl", "girls", "boy", "boys", "kid", "kids", "someone", "everyone",
                     "creator", "influencer", "team", "crowd", "audience", "character", "human", "humans",
                     "face", "faces", "facial", "head", "hand", "hands", "finger", "fingers", "arm", "arms",
                     "body", "eyes", "eye", "mouth", "smile", "smiling", "selfie", "portrait", "expression",
                     "confused", "annoyed", "angry", "happy", "sad", "puzzled", "frustrated", "shocked",
                     "surprised", "crying", "laughing", "worried", "excited", "nervous", "stressed",
                     "thinking", "staring", "looking", "holding", "pointing", "nodding", "shrugging",
                     "concerned", "look", "looks", "shakes", "shaking", "sighs", "sighing", "frowns",
                     "frowning", "grins", "grinning", "panics", "panicking", "celebrates", "celebrating",
                     "cheering", "waves", "waving", "scratching", "facepalm", "facepalms", "rolls", "eye-roll",
                     "talking", "speaking", "reacting", "sitting", "standing", "walking"], None),
}


def remove_people(text: str) -> str:
    """Drop/replace person, body-part and expression words; keep everything else in order."""
    out = []
    for token in re.findall(r"[A-Za-z][A-Za-z'-]*|\S", text):
        key = token.lower().strip("'")
        if key.endswith("'s"):
            key = key[:-2]
        if key in PEOPLE_WORDS:
            swap = PEOPLE_WORDS[key]
            if swap and swap not in out:
                out.append(swap)
            continue
        out.append(token)
    return re.sub(r"\s+([,.;:!?])", r"\1", " ".join(out)).strip(" ,.;:-")


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


def fallback_queries(clip_idea: str, voiceover: str, n: int, people: bool = True) -> list[str]:
    """Keyword queries, one per shot, varied so shots don't repeat."""
    if not people:
        clip_idea, voiceover = remove_people(clip_idea), remove_people(voiceover)
    words = keywords(clip_idea, 8) or keywords(voiceover, 8) or ["abstract", "background"]
    queries = []
    for i in range(n):
        # Slide a 3-word window over the keywords, then vary the framing
        window = words[i % max(1, len(words) - 2):][:3] or words[:3]
        variation = SHOT_VARIATIONS[i % len(SHOT_VARIATIONS)]
        queries.append(" ".join(window + ([variation] if variation else [])))
    return queries


def llm_queries(clip_idea: str, voiceover: str, n: int, niche: str = "",
                people: bool = True) -> list[str]:
    """Ask the local LLM for `n` short stock-footage queries. Raises on failure."""
    from pipeline.local_llm import chat_json

    subjects = ("concrete, filmable things (people, objects, places, actions)" if people else
                "concrete, filmable OBJECTS and PLACES only (devices, screens, desks, tools, rooms, "
                "landscapes); NO people, faces, hands, bodies or characters — show the object instead "
                "of the person using it")
    prompt = (
        f"A short vertical video scene needs {n} consecutive B-roll shots.\n"
        f"Niche: {niche or 'general'}\n"
        f"Scene visual idea: {clip_idea}\n"
        f"Voiceover during the scene: {voiceover}\n\n"
        f"Write exactly {n} stock-footage search queries, one per shot, in order.\n"
        f"Rules: 2-5 words each; {subjects};\n"
        "no abstract words, no text/graphics, no camera jargon; shots must differ from each other.\n"
        'Return JSON: {"queries": ["...", "..."]}'
    )
    result = chat_json(prompt, system="You are a video editor choosing stock footage.",
                       temperature=0.4, max_tokens=200)
    queries = [q.strip() for q in result.get("queries", []) if isinstance(q, str) and q.strip()]
    if not people:   # the LLM doesn't always obey; scrub what slipped through
        queries = [remove_people(q) for q in queries]
        queries = [q for q in queries if keywords(q)]
    if len(queries) < n:
        raise ValueError(f"LLM returned {len(queries)} queries, needed {n}")
    return [" ".join(q.split()[:6]) for q in queries[:n]]


def plan_queries(clip_idea: str, voiceover: str, n: int, niche: str = "",
                 use_llm: bool = True, people: bool = True) -> tuple[list[str], str]:
    """Return (queries, source) where source is 'llm' or 'keywords'."""
    if use_llm:
        try:
            return llm_queries(clip_idea, voiceover, n, niche, people=people), "llm"
        except Exception as e:
            print(f"[ShotPlanner] LLM queries unavailable ({e}); using keyword fallback")
    return fallback_queries(clip_idea, voiceover, n, people=people), "keywords"


def image_prompt(query: str, clip_idea: str, look: list[str] | None = None,
                 people: bool = True) -> str:
    """
    Prompt for the image model: (creator's medium), shot query, scene context,
    the creator's other look words (personalised only), then the quality suffix.
    A stylised medium (e.g. "3D animated render") leads the prompt, where SDXL
    weighs it most, and replaces "photorealistic".
    """
    look = list(look or [])
    medium = next((m for m in look if m in STYLISED_MEDIA), None)
    style = IMAGE_STYLE.replace("photorealistic, ", "") if medium else IMAGE_STYLE
    look = [t for t in look if t != medium and t != "photorealistic photo"]
    if not people:
        query, clip_idea = remove_people(query), remove_people(clip_idea)
        style = f"{style}, {OBJECT_STYLE}"
    # Look words before the scene keywords: SDXL weighs early tokens most, and the
    # creator's lighting (e.g. "dark moody") must beat the default bright desk scene
    parts = [medium, query, ", ".join(look), " ".join(keywords(clip_idea, 6)), style]
    return ", ".join(p for p in parts if p)
