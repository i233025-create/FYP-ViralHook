"""
urdu_style.py — Creator style from Urdu / Urdu–English (Roman Urdu) transcripts
================================================================================
Pakistani creators mix Urdu and English. The English transcript (Whisper
language="en") is right for RETRIEVAL (experiment E1), but it is a
translation: "kharcha hogaya ustaad" becomes "it was expensive, man", so the
creator's own words, catchphrases and Urdu–English mix are lost. This module
keeps them, for STYLE:

  romanize()     Whisper's Urdu-script (Nastaliq) transcript → Roman Urdu as
                 Pakistanis type it, English words written in English
                 ("شوپ" → "shop"). Local LLM (pipeline.local_llm), with the
                 reel's English translation as a hint for which words were
                 spoken in English.
  style_card()   Measured, reproducible style markers (no LLM):
                   english_ratio      share of English words (overall and in
                                      hook / body / end)
                   catchphrases       2–8-word phrases the creator repeats
                                      across reels (and, with a background of
                                      other creators, that others don't use)
                   openers / closers  how reels typically start and end
                   address            how the viewer is addressed (dosto, aap,
                                      guys, ...), per 100 words
                   avg_sentence_words
                   written            caption stats (creator-written text), if
                                      captions are given
  card_prompt()  the card as instructions for the Scripting Agent's prompt.

English vs Urdu words (Roman script): a word is English when it is in an
English word list (pipeline/data/english_words.txt.gz) and not in the Roman
Urdu lexicon. The lexicon is a built-in list of common Roman Urdu words and
spelling variants, plus the creator's short words that look English but are
Urdu for them ("bat" = baat, "rat" = raat): ≤3 letters and absent from that
reel's English translation. Everything else (tikka, gosht, ustaad, any
spelling variant) counts as Urdu. The English translation alone cannot decide
it, because Whisper paraphrases ("food", "video" are often missing from it).
It is a heuristic, applied the same way to the creator's transcripts and to
generated scripts, so the two are comparable.
"""

from __future__ import annotations

import difflib
import gzip
import math
import re
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path

# ─── Script detection ──────────────────────────────────────────────────────────

_ARABIC_RE = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_TOKEN_RE = re.compile(r"[a-z0-9']+")
_SENTENCE_RE = re.compile(r"(?<=[.!?۔؟])\s+")


def arabic_script_share(text: str) -> float:
    """Share of letters written in Arabic script (Urdu Nastaliq) — 0.0 for Roman text."""
    arabic = len(_ARABIC_RE.findall(text or ""))
    latin = len(_LATIN_RE.findall(text or ""))
    return arabic / (arabic + latin) if arabic + latin else 0.0


def tokens(text: str) -> list[str]:
    """Lower-cased Latin-script word tokens (Roman Urdu and English alike)."""
    return _TOKEN_RE.findall((text or "").lower().replace("’", "'"))


def sentences(text: str) -> list[str]:
    return [s for s in _SENTENCE_RE.split((text or "").strip()) if tokens(s)]


# ─── Roman Urdu lexicon ────────────────────────────────────────────────────────

# Function words and very common words, with the spelling variants people type.
# Words that are also everyday English ("to", "is", "us", "main", "me") are
# included — in a Roman Urdu transcript they are far more often Urdu.
ROMAN_URDU_COMMON = frozenset("""
hai hain he hay hy ha tha thi thay the thy ho hon hun hoon hota hoti hotay hote hua hui huay hue
hogaya hogayi hogaye hogya hogyi gaya gayi gaye gya gyi geya jata jati jate jaata jaati jaana jana
ka ki ke kay ko se say mein main me mai mujhe mujhy mjhe mera meri mere meray hum ham humein hamein
humara hamara humari hamari tum tumhe tumhein tumhara tumhari tu tera teri tere aap ap apka aapka
apki aapki apke aapke apna apni apne apnay unka unki unke inka inki inke woh wo vo voh yeh ye yah
is us iss uss in un inn unn isko usko inko unko isay usay isse usse
aur or bhi bi to tou toh na nah nahi nahin nai nhi mat sirf bas bus phir fir pher abhi ab jab tab kab
kya kia kyun kyu kyon kaise kese kaisa kesa kaisi kesi kahan kidhar kaun kon kitna kitni kitne
koi kuch kuchh sab sabhi sara sari saray sare har bohat bahut boht bht zyada ziada zada kam thoda
thora thori thodi zara bilkul sach jhoot acha achha accha achi achhi ache achay bura buri bure
kar karo karna karni karne karte karta karti kartay karain karein karen kiya kiye kiyay kia kie kr
de do dena deni dete deta deti diya diye dia die le lo lena leni lete leta leti liya liye lia lie
raha rahi rahe rahay rahey reh rehna rehta rehti chal chalo chalein chalen chala chali chalte
dekho dekhna dekha dekhi dekhte dekhiye suno suna suni sunte bolo bola boli bolte bata batao bataya
batana samajh samjho samjha samjhe pata pta chahiye chahie chahte chahta chahti sakta sakti sakte
lagta lagti lagte laga lagi lage mil mila mili mile milta milti milte aa aaya aayi aaye aai aye ai
aata aati aate ata ati aate jao jayen jaen jaye jae ga gi ge gay
yahan yahaan wahan wahaan idhar udhar upar neeche andar bahar saath sath pehle pehlay baad
aaj kal parson subah sham raat din waqt time kabhi hamesha
dosto doston dost yaar yar yaaro yaro bhai bhaiyo bhaiyon behen behno janab sahab sahib ji jee
haan han haa nahi jaisa jaisi jaise jese jesa waisa waise lekin magar par pr kyunke kyunki kyonke
agar warna taake taakay yani matlab shayad zaroor zarur
ek aik do teen char paanch panch chay saat aath nau das sau hazaar
log logon logo cheez cheezein cheezen baat baatein batein kaam kam ghar khana pani paisa paise
dil zindagi duniya
wala wali wale walay vala vali vale bana bani bane banay pure poore pura poora puri poori khan
""".split())

ADDRESS_TERMS = ("dosto", "doston", "guys", "yaar", "yaaro", "bhai", "bhaiyo", "aap", "ap",
                 "tum", "tu", "you", "janab", "friends")

# Short words that never make a catchphrase on their own.
_STOP = frozenset("""
hai hain he ha tha thi the ho hon ka ki ke ko se mein main me to tou toh bhi aur or ye yeh wo woh
is us ek na nahi hum aap tum mera meri mere
a an and the of to in is it that this for on with as at be are was were i you we they he she
so but if or my your our just
""".split())


ENGLISH_WORDS_FILE = Path(__file__).parent / "data" / "english_words.txt.gz"
SHORT_HOMOGRAPH = 3     # English-looking words this short may be Urdu ("bat" = baat)


@lru_cache(maxsize=1)
def english_words() -> frozenset:
    """The English word list (lower case)."""
    with gzip.open(ENGLISH_WORDS_FILE, "rt", encoding="utf-8") as f:
        return frozenset(line.strip() for line in f if line.strip())


def is_english(word: str, lexicon: frozenset = ROMAN_URDU_COMMON) -> bool:
    return word not in lexicon and word in english_words()


def build_lexicon(roman_texts: list[str], english_texts: list[str] | None = None) -> frozenset:
    """
    Roman Urdu vocabulary for one creator: the built-in list plus the words of
    their Roman transcripts that the matching English translation does not
    contain (not spoken in English) — non-English words, and short words that
    only look English ("bat" = baat). Longer English words ("food", "video")
    stay English even when the translation paraphrased them away.
    `english_texts[i]` is the English transcript of the same reel as `roman_texts[i]`.
    """
    english_texts = english_texts or []
    english = english_words()
    learned = set()
    for i, roman in enumerate(roman_texts):
        english_vocab = set(tokens(english_texts[i])) if i < len(english_texts) else set()
        if not english_vocab:
            continue    # nothing to tell English words apart with
        learned.update(w for w in tokens(roman)
                       if w not in english_vocab and not w.isdigit()
                       and (w not in english or len(w) <= SHORT_HOMOGRAPH))
    return frozenset(ROMAN_URDU_COMMON | learned)


def english_ratio(text: str, lexicon: frozenset = ROMAN_URDU_COMMON) -> float:
    """Share of words that are English (see is_english; digits ignored)."""
    words = [w for w in tokens(text) if not w.isdigit()]
    if not words:
        return 0.0
    return sum(is_english(w, lexicon) for w in words) / len(words)


HOOK_WORDS = 12    # first words = hook, last words = ending


def segment_english_ratios(text: str, lexicon: frozenset = ROMAN_URDU_COMMON) -> dict:
    """English share in the hook (first 12 words), body and end (last 12 words)."""
    words = [w for w in tokens(text) if not w.isdigit()]
    if not words:
        return {"hook": 0.0, "body": 0.0, "end": 0.0}

    def share(ws: list[str]) -> float:
        return sum(is_english(w, lexicon) for w in ws) / len(ws) if ws else 0.0

    body = words[HOOK_WORDS:-HOOK_WORDS] if len(words) > 2 * HOOK_WORDS else words
    return {"hook": share(words[:HOOK_WORDS]), "body": share(body), "end": share(words[-HOOK_WORDS:])}


# ─── Style card ────────────────────────────────────────────────────────────────

# A catchphrase does not start or end on a postposition / particle: "ko to bhai",
# "batao ke", "bait mein" are pieces cut out of longer sentences. (Ending on a
# verb is fine: Urdu is verb-final, "kaho ge", "try karo".)
_DANGLING = frozenset("""
ko ke ki ka kay se say mein me main par pe pr ne aur or jo to tou toh bhi ya
is us iss uss ek aik ye yeh wo woh the a an and of to in for with at
""".split())


def _is_fragment(words: tuple[str, ...]) -> bool:
    """
    A cut-off piece, or grammar only: no word beyond common Roman Urdu / stop
    words. An unknown 1–2-letter word at either end is a mis-heard word cut in
    half ("batao ke ar" from "batao ke R-U team").
    """
    if words[0] in _DANGLING or words[-1] in _DANGLING:
        return True
    if any(len(w) <= 2 and w not in ROMAN_URDU_COMMON and w not in _STOP for w in (words[0], words[-1])):
        return True
    return all(w in ROMAN_URDU_COMMON or w in _STOP for w in words)


def _ngrams(words: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def catchphrases(texts: list[str], background: list[str] | None = None,
                 sizes: tuple[int, ...] = tuple(range(2, 9)), min_reels: int = 2,
                 top: int = 10, exclude: list[str] | None = None) -> list[dict]:
    """
    Phrases the creator repeats across reels (document frequency ≥ min_reels).
    With `background` (other creators' transcripts) a phrase must also be more
    common for this creator than for the others — removes "you know", "kya hai".
    Fragments are dropped (starting / ending on a postposition such as "ko",
    "mein", or made only of common grammar words like "kar rahay hain"), and a shorter phrase is
    dropped when a longer one containing it occurs in as many reels — so a
    repeated sign-off comes out whole ("bas yahi tha aaj ka"), not as
    overlapping 3-word pieces. Phrases are 2–8 words. Words of an `exclude`
    phrase (the creator's opener / sign-off) are not counted, so the phrases
    around it still come out ("kharcha hogaya ustaad" before "bas yahi tha aaj ka").
    """
    docs = [tokens(t) for t in texts if tokens(t)]
    if len(docs) < min_reels:
        return []
    bg_docs = [tokens(t) for t in background or [] if tokens(t)]
    excluded = [tokens(p) for p in exclude or [] if tokens(p)]

    df: Counter = Counter()
    for words in docs:
        covered = _covered(words, excluded)
        for n in sizes:
            df.update({tuple(words[i:i + n]) for i in range(len(words) - n + 1)
                       if not any(covered[i:i + n])})
    bg_df: Counter = Counter()
    for words in bg_docs:
        for n in sizes:
            bg_df.update(_ngrams(words, n))

    candidates = []
    for gram, count in df.items():
        if count < min_reels or _is_fragment(gram):
            continue
        share = count / len(docs)
        bg_share = bg_df[gram] / len(bg_docs) if bg_docs else 0.0
        distinct = share - bg_share
        if bg_docs and distinct <= 0:
            continue
        candidates.append((gram, count, share, bg_share, distinct))

    # Longest first, so containment can be checked against kept phrases.
    candidates.sort(key=lambda c: (-len(c[0]), -c[1]))
    kept: list[tuple] = []
    for cand in candidates:
        phrase = " ".join(cand[0])
        if any(phrase in " ".join(k[0]) and cand[1] <= k[1] for k in kept):
            continue
        kept.append(cand)

    kept.sort(key=lambda c: (-c[4], -c[1], -len(c[0])))
    return [{"phrase": " ".join(g), "reels": c, "share": round(s, 3), "background_share": round(b, 3),
             "example": _in_context(g, docs)}
            for g, c, s, b, _ in kept[:top]]


EXAMPLE_MAX_WORDS = 7   # phrase + context stays under the 8-word copy check (COPY_NGRAM)


def _in_context(gram: tuple[str, ...], docs: list[list[str]]) -> str:
    """
    The phrase with a few of the creator's words around it, from the first reel
    that has it. Short enough (EXAMPLE_MAX_WORDS) that copying the example
    whole is not a word-for-word copy of the creator's video.
    """
    n = len(gram)
    side = max(0, (EXAMPLE_MAX_WORDS - n) // 2)
    for words in docs:
        for i in range(len(words) - n + 1):
            if tuple(words[i:i + n]) == gram:
                left = words[max(0, i - side):i]
                right = words[i + n:i + n + side]
                return " ".join(["..."] * bool(left) + left + list(gram) + right + ["..."] * bool(right))
    return " ".join(gram)


OPENER_WINDOW = 6      # an opener is said within the first 6 words of a reel
CLOSER_WINDOW = 8      # a sign-off within the last 8
EDGE_MIN_SHARE = 0.2   # ... in at least 20% of the reels (and at least 2)


def _covered(words: list[str], phrases: list[list[str]]) -> list[bool]:
    """Positions of `words` inside an occurrence of any of `phrases`."""
    covered = [False] * len(words)
    for phrase in phrases:
        n = len(phrase)
        for i in range(len(words) - n + 1):
            if words[i:i + n] == phrase:
                covered[i:i + n] = [True] * n
    return covered


def _edge_phrases(texts: list[str], first: bool, min_count: int = 2,
                  sizes: tuple[int, ...] = (2, 3, 4, 5)) -> list[dict]:
    """
    Phrases said at the start (or end) of at least `min_count` reels: 2–5-word
    n-grams inside the first OPENER_WINDOW (last CLOSER_WINDOW) words. A
    greeting may come after a word or two ("haan ji bhatti army ...") and ASR
    spells its tail differently from reel to reel, so this is not "the first
    3 words". Picked greedily (most reels, then longest); a phrase sharing a
    word with one already picked is a piece of it and is dropped.
    """
    window = OPENER_WINDOW if first else CLOSER_WINDOW
    counts: Counter = Counter()
    for t in texts:
        words = tokens(t)
        edge = words[:window] if first else words[-window:]
        counts.update({" ".join(g) for n in sizes for g in _ngrams(edge, n)})
    candidates = sorted(((p, c) for p, c in counts.items()
                         if c >= min_count and not all(w in _STOP for w in p.split())),
                        key=lambda pc: (-pc[1], -len(pc[0].split()), pc[0]))
    kept: list[tuple[str, int]] = []
    used: set[str] = set()
    for phrase, count in candidates:
        words = set(phrase.split()) - _STOP
        if words & used:
            continue
        kept.append((phrase, count))
        used |= words
    return [{"phrase": p, "reels": c} for p, c in kept[:5]]


JOIN_SHARE = 0.75


def _join_edge(texts: list[str], edges: list[dict], first: bool, min_count: int) -> list[dict]:
    """
    Join the top two edge phrases when they are one phrase said together: ASR
    spells a greeting's tail differently from reel to reel, so "bhati armi"
    (5 reels) and "pakhir raglay" (4) come out apart although the creator
    says "bhati armi pakhir raglay". Joined when the pair is adjacent at the
    start (end) of at least `min_count` reels and of most (JOIN_SHARE) of the
    reels with the top phrase — a catchphrase that only sometimes runs into the
    sign-off stays separate.
    """
    if len(edges) < 2:
        return edges
    a, b = edges[0]["phrase"], edges[1]["phrase"]
    joined = f"{a} {b}" if first else f"{b} {a}"
    window = OPENER_WINDOW + len(b.split()) if first else CLOSER_WINDOW + len(b.split())
    count = sum(1 for t in texts
                if f" {joined} " in " " + " ".join(tokens(t)[:window] if first else tokens(t)[-window:]) + " ")
    if count < max(min_count, JOIN_SHARE * edges[0]["reels"]):
        return edges
    return [{"phrase": joined, "reels": count}] + edges[2:]


MAX_SENTENCE_WORDS = 40    # above this the transcript has no punctuation (Whisper's Urdu output)


def address_rates(text: str) -> dict:
    """Uses per 100 words of each way of addressing the viewer (only those used)."""
    words = tokens(text)
    if not words:
        return {}
    counts = Counter(w for w in words if w in ADDRESS_TERMS)
    return {term: round(100 * c / len(words), 2) for term, c in counts.most_common()}


def _written_stats(captions: list[str], lexicon: frozenset) -> dict:
    texts = [re.sub(r"https?://\S+|[@#]\w+", " ", c or "") for c in captions]
    texts = [t for t in texts if tokens(t)]
    if not texts:
        return {}
    emoji = re.compile(r"[\U0001F300-\U0001FAFF☀-➿]")
    return {
        "captions": len(texts),
        "english_ratio": round(english_ratio(" ".join(texts), lexicon), 3),
        "avg_words": round(sum(len(tokens(t)) for t in texts) / len(texts), 1),
        "hashtags_per_caption": round(sum(len(re.findall(r"#\w+", c or "")) for c in captions)
                                      / len(captions), 2),
        "emoji_per_caption": round(sum(len(emoji.findall(c or "")) for c in captions) / len(captions), 2),
    }


def style_card(roman_texts: list[str], english_texts: list[str] | None = None,
               captions: list[str] | None = None, background: list[str] | None = None) -> dict:
    """
    Measured style of one creator from their Roman Urdu transcripts.

    Args:
        roman_texts:   one Roman Urdu (code-mixed) transcript per reel.
        english_texts: the English transcripts of the same reels (same order),
                       used to learn which words the creator speaks in Urdu.
        captions:      creator-written captions (written style), optional.
        background:    other creators' Roman transcripts, for distinct catchphrases.
    """
    texts = [t for t in roman_texts if tokens(t)]
    lexicon = build_lexicon(roman_texts, english_texts)
    if not texts:
        return {"reels": 0}
    joined = " ".join(texts)
    segments = [segment_english_ratios(t, lexicon) for t in texts]
    sents = [s for t in texts for s in sentences(t)]
    avg_sentence = round(len(tokens(joined)) / max(len(sents), 1), 1)
    min_edge = max(2, math.ceil(EDGE_MIN_SHARE * len(texts)))
    openers = _join_edge(texts, _edge_phrases(texts, first=True, min_count=min_edge), True, min_edge)
    closers = _join_edge(texts, _edge_phrases(texts, first=False, min_count=min_edge), False, min_edge)
    card = {
        "reels": len(texts),
        "words": len(tokens(joined)),
        "english_ratio": round(english_ratio(joined, lexicon), 3),
        "english_ratio_by_part": {part: round(sum(s[part] for s in segments) / len(segments), 3)
                                  for part in ("hook", "body", "end")},
        # an opener / sign-off goes in its own slot, not in the mid-script phrases
        "catchphrases": catchphrases(texts, background,
                                     exclude=[e[0]["phrase"] for e in (openers, closers) if e]),
        "openers": openers,
        "closers": closers,
        "address": address_rates(joined),
        # None: unpunctuated transcripts, sentence length unknown
        "avg_sentence_words": avg_sentence if avg_sentence <= MAX_SENTENCE_WORDS else None,
    }
    if captions:
        card["written"] = _written_stats(captions, lexicon)
    return card


def strip_opener(text: str, opener: str, min_similarity: float = 0.6) -> str:
    """
    `text` without the creator's greeting at its start ("Bhati Armee pakhir
    raglay, ye shop..." → "ye shop..."). Words are compared loosely, because
    the LLM and ASR spell the greeting differently; at least 3/4 of its words
    must match. Returns `text` unchanged when it does not start with the greeting.
    """
    greeting = tokens(opener)
    spans = list(re.finditer(r"[A-Za-z0-9']+", text or ""))
    if not greeting or len(spans) < len(greeting):
        return text
    head = [m.group().lower() for m in spans[:len(greeting)]]
    similar = sum(difflib.SequenceMatcher(None, a, b).ratio() >= min_similarity
                  for a, b in zip(head, greeting))
    if similar < math.ceil(0.75 * len(greeting)):
        return text
    return text[spans[len(greeting) - 1].end():].lstrip(" ,.!-—:;")


def opener_phrase(card: dict | None) -> str:
    """The creator's greeting from a style card, "" if none."""
    openers = (card or {}).get("openers") or []
    return openers[0]["phrase"] if openers else ""


def mix_label(ratio: float) -> str:
    return ("mostly English with some Urdu" if ratio >= 0.65 else
            "an even Urdu–English mix" if ratio >= 0.35 else
            "mostly Urdu with English words mixed in")


# Catchphrases and the greeting are measured from speech-recognition output, so
# their spelling is the recogniser's ("farsh bait" for "first bite"). A local
# model cannot reliably fix them on its own (tested), but it can respell them
# while writing when told they may be misspelled.
ASR_SPELLING_NOTE = ("SPELLING: the phrases and greeting above were taken from speech recognition and may be "
                     "misspelled. When you use them, write English words in correct English spelling "
                     "(\"first bite\", not \"farsh bait\"; \"try\", not \"daray\") and Urdu words in common "
                     "Roman Urdu spelling.")


def card_prompt(card: dict) -> str:
    """The style card as concrete instructions for the script writer."""
    if not card.get("reels"):
        return ""
    ratio = card["english_ratio"]
    parts = [f"LANGUAGE: this creator speaks {mix_label(ratio)} (~{ratio:.0%} English words). "
             "Write every voiceover and caption in Roman Urdu (Urdu in Latin letters, the way "
             "Pakistanis type it) mixed with English in that same proportion — never in Urdu "
             "script, never pure English. Keep clip_idea in plain English."]
    by_part = card.get("english_ratio_by_part") or {}
    if by_part:
        parts.append(f"Their hooks are ~{by_part['hook']:.0%} English, the middle ~{by_part['body']:.0%}, "
                     f"the ending ~{by_part['end']:.0%}.")
    if card.get("catchphrases"):
        uses = "; ".join(f'"{c["phrase"]}" (as in: "{c.get("example") or c["phrase"]}")'
                         for c in card["catchphrases"][:5])
        parts.append("CATCHPHRASES they repeat across their videos, with how they say them: "
                     f"{uses}. Use at most one or two, inside a full sentence the way they use it — "
                     "never tack a phrase onto the end of an unrelated sentence.")
    if card.get("catchphrases") or card.get("openers"):
        parts.append(ASR_SPELLING_NOTE)
    if card.get("openers"):
        opener = card["openers"][0]["phrase"]
        parts.append(f'OPENER: they often start a reel with the greeting "{opener} ..." — begin the scene 1 '
                     "voiceover with it, then the hook sentence after it. It is a greeting, not a name or topic: "
                     "never use it anywhere else in the script.")
    if card.get("closers"):
        closer = card["closers"][0]["phrase"]
        parts.append(f'SIGN-OFF: they often end with "... {closer}" — end the last voiceover that way.')
    if card.get("address"):
        parts.append("They address the viewer as: " + ", ".join(list(card["address"])[:4]) + ".")
    return " ".join(parts)


# ─── Romanization (local LLM) ──────────────────────────────────────────────────

ROMANIZE_SYSTEM = ("You transliterate Pakistani speech transcripts from Urdu script into Roman Urdu. "
                   "You never translate and never summarise.")

ROMANIZE_PROMPT = """Rewrite this Urdu-script transcript of a Pakistani creator's video in Roman Urdu
(Urdu written in Latin letters, the way Pakistanis type on WhatsApp/Instagram).

Rules:
1. Transliterate, do NOT translate: Urdu words stay Urdu ("آج ہم" -> "aaj hum").
2. English words the speaker said were written in Urdu letters by the speech recogniser — write
   them as normal English words ("شوپ" -> "shop", "سپیسی" -> "spicy", "ویڈیو" -> "video").
   The English translation below shows roughly what was said; use it ONLY to recognise such
   English words, never copy its sentences.
3. Punjabi / Pashto / Sindhi words: transliterate them as they sound, do not replace them.
4. Keep every word and the order. Add normal punctuation (. ? !) where sentences end.
5. Common spellings: hai, hain, nahi, kya, bhi, ke, ki, ka, ko, se, mein, aur, yeh, woh, aap, hum.
6. Plain a-z letters only: no accents or phonetic symbols ("chaawal", not "chāvl").

URDU TRANSCRIPT:
{urdu}

ENGLISH TRANSLATION (hint only):
{english}

Return JSON: {{"roman": "<the Roman Urdu transcript>"}}"""

CHUNK_WORDS = 90            # Urdu words per LLM call (small local models drift on long input)
ENGLISH_HINT_CHARS = 1500
MAX_ARABIC_SHARE = 0.1      # output still in Urdu script above this → retry / fail


_IPA_TO_ASCII = str.maketrans({"ɪ": "i", "ʊ": "u", "ə": "a", "ɛ": "e", "ɔ": "o", "ʃ": "sh", "ŋ": "ng", "ɑ": "a"})


def plain_latin(text: str) -> str:
    """Strip accents / phonetic symbols the LLM sometimes adds (ā→a, ṭ→t, ẖ→h, ɪ→i)."""
    decomposed = unicodedata.normalize("NFKD", text.translate(_IPA_TO_ASCII))
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


class RomanizeError(RuntimeError):
    """The LLM did not return a usable Roman Urdu transcript."""


def _chunks(text: str, size: int = CHUNK_WORDS) -> list[str]:
    """Split at sentence ends (۔ ؟ . ? !) into chunks of about `size` words."""
    pieces = re.split(r"(?<=[۔؟.?!])\s+", text.strip())
    chunks, current = [], []
    for piece in pieces:
        words = piece.split()
        # Whisper's Urdu output often has no punctuation: cut long pieces by words.
        while len(words) > size:
            if current:
                chunks.append(" ".join(current))
                current = []
            chunks.append(" ".join(words[:size]))
            words = words[size:]
        if current and len(current) + len(words) > size:
            chunks.append(" ".join(current))
            current = []
        current.extend(words)
    if current:
        # A short tail on its own makes the LLM drift back into Urdu script: merge it.
        if chunks and len(current) < size // 2:
            chunks[-1] += " " + " ".join(current)
        else:
            chunks.append(" ".join(current))
    return chunks


def romanize(urdu: str, english: str = "", model: str | None = None, chat=None, retries: int = 1) -> str:
    """
    Urdu-script transcript → Roman Urdu with English words in English.
    Text that is already mostly Latin is returned unchanged.

    Args:
        urdu:    Whisper transcript with language="ur".
        english: Whisper transcript of the same reel with language="en" (hint).
        model:   Ollama model override (e.g. "qwen2.5:14b"); default from .env.
        chat:    chat_json-compatible callable (tests inject a fake).

    Raises:
        RomanizeError: the LLM kept answering in Urdu script or with no text.
    """
    if not (urdu or "").strip():
        return ""
    if arabic_script_share(urdu) < MAX_ARABIC_SHARE:
        return urdu.strip()
    if chat is None:
        from pipeline.local_llm import chat_json as chat

    hint = (english or "").strip()[:ENGLISH_HINT_CHARS] or "(not available)"
    out = []
    for chunk in _chunks(urdu):
        for attempt in range(retries + 1):
            try:
                result = chat(ROMANIZE_PROMPT.format(urdu=chunk, english=hint), system=ROMANIZE_SYSTEM,
                              temperature=0.1 + 0.3 * attempt, max_tokens=800, model=model)
            except Exception as e:      # LLM unreachable / bad JSON
                if attempt == retries:
                    raise RomanizeError(f"romanize failed: {e}") from e
                continue
            roman = plain_latin(str(result.get("roman", "")).strip())
            if roman and arabic_script_share(roman) < MAX_ARABIC_SHARE:
                out.append(roman)
                break
            if attempt == retries:
                raise RomanizeError(f"LLM did not return Roman Urdu for: {chunk[:60]}...")
    return " ".join(out)
