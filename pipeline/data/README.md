# pipeline/data

`english_words.txt.gz` — lower-case English words (63,859), one per line, used by
`pipeline/urdu_style.py` to tell English words from Roman Urdu. Built from the
Debian `wamerican` list (SCOWL, Copyright 2000–2011 Kevin Atkinson et al.,
permissive licence) plus a few social-media words (vlog, youtube, reels, ...):

    grep -x "[a-z]*" /usr/share/dict/american-english | sort -u | gzip -9n > english_words.txt.gz
