"""
text_clean.py — Turn a raw Instagram caption into a search query
=================================================================
Reels have no titles, so E1 uses the caption as the query. Raw captions
carry a lot that says nothing about the topic:

  "This serum changed my skin 😍✨ Link in bio! #skincare @brand"
      → "This serum changed my skin"

Removed: URLs, @mentions, #hashtags, emojis/symbols, and call-to-action
boilerplate ("link in bio", "follow for more", ...). Urdu/Hindi script
letters are kept — only symbol characters are stripped.

Also reports which script a text is written in (Latin / Arabic / Devanagari),
used to check what Whisper produced for code-mixed Urdu–English speech.
"""

from __future__ import annotations

import re
import unicodedata

MIN_QUERY_WORDS = 4

URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
MENTION_RE = re.compile(r"@[\w.]+")
HASHTAG_RE = re.compile(r"#\w+")

# Call-to-action lines that appear on reels regardless of topic.
BOILERPLATE = [
    r"link in (?:my )?bio",
    r"follow (?:me |us )?for more(?: \w+){0,2}",
    r"follow @?\w+ for more",
    r"(?:like|save|share)(?:,? (?:and|&) (?:like|save|share|follow))+(?: this)?(?: post| reel| video)?",
    r"save this (?:post|reel|video)(?: for later)?",
    r"share (?:this )?with (?:a|your) (?:friend|bestie|bff)s?(?: who \w+)?",
    r"comment (?:below|\"?\w+\"?)(?: (?:below|for (?:the )?link))?",
    r"dm (?:me )?for (?:collab|collabs|business|link)s?",
    r"tag (?:a|your) (?:friend|bestie)s?(?: who \w+)?",
    r"turn on (?:post )?notifications",
    r"products mentioned:?",
    r"mentioned in the video:?",
    r"location pin in comments",
]
# Symbols left behind once mentions/hashtags are gone: "Islamabad &", "Team- @".
STRAY_RE = re.compile(r"(?<!\S)[@&|•·]+(?!\S)|(?<=\s)[-–—]+(?=\s*[,.]|$)|(?<!\S)[,.]+(?!\S)")
BOILERPLATE_RE = re.compile(r"\b(?:" + "|".join(BOILERPLATE) + r")(?!\w)[!.]*", re.IGNORECASE)


def _strip_symbols(text: str) -> str:
    """Drop emojis and other pictographic symbols; keep letters, digits, punctuation."""
    out = []
    for ch in text:
        category = unicodedata.category(ch)
        # So = other symbol (emoji), Sk = modifier symbol, Cf = format chars
        # (zero-width joiner, variation selectors), Co = private use.
        if category in ("So", "Sk", "Co") or ch in "‍️︎":
            out.append(" ")
        else:
            out.append(ch)
    return "".join(out)


def clean_caption(caption: str) -> str:
    """Raw Instagram caption → topic text usable as a search query."""
    text = caption or ""
    text = URL_RE.sub(" ", text)
    text = MENTION_RE.sub(" ", text)
    text = HASHTAG_RE.sub(" ", text)
    text = _strip_symbols(text)
    text = BOILERPLATE_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    text = STRAY_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Leftover punctuation-only fragments at the ends ("| ", "- ", "!!").
    return text.strip(" |-–—:;,.!?")


def word_count(text: str) -> int:
    return len(re.findall(r"\w+", text or ""))


def detect_script(text: str) -> dict[str, float]:
    """Share of letters in each script — Latin, Arabic (Urdu), Devanagari (Hindi)."""
    counts = {"latin": 0, "arabic": 0, "devanagari": 0, "other": 0}
    for ch in text or "":
        if not ch.isalpha():
            continue
        name = unicodedata.name(ch, "")
        if name.startswith("LATIN"):
            counts["latin"] += 1
        elif name.startswith("ARABIC"):
            counts["arabic"] += 1
        elif name.startswith("DEVANAGARI"):
            counts["devanagari"] += 1
        else:
            counts["other"] += 1
    total = sum(counts.values())
    return {k: round(v / total, 3) if total else 0.0 for k, v in counts.items()}


def dominant_script(text: str) -> str:
    shares = detect_script(text)
    if not any(shares.values()):
        return "none"
    return max(shares, key=shares.get)
