"""Direct test - bypasses server to verify the 3-window approach works."""
import sys, math
sys.path.insert(0, '.')

from pipeline.agents.research_agent import research_agent, _expand_keywords
import pipeline.agents.research_agent as _ra
from pipeline.state import PipelineState

niche = "Beauty"
all_keywords = _expand_keywords(niche)
print(f"Keywords for '{niche}': {all_keywords}\n")

extra_keywords = ["trending shorts ideas", "viral content strategy",
                  "content creation tips", "social media growth", "reel ideas"]
all_keywords_extended = all_keywords + [kw for kw in extra_keywords if kw not in all_keywords]

chunk = max(3, math.ceil(len(all_keywords_extended) / 3))
keyword_windows = [
    all_keywords_extended[0:chunk],
    all_keywords_extended[chunk:chunk*2] or all_keywords_extended[-chunk:],
    all_keywords_extended[chunk*2:] or all_keywords_extended[-chunk:],
]

print("Keyword windows:")
for i, w in enumerate(keyword_windows):
    print(f"  Window {i+1}: {w}")
print()

topics = []
seen = set()

for i, kw_window in enumerate(keyword_windows):
    print(f"\n--- Run {i+1} | keywords: {kw_window} ---")
    _original = _ra._expand_keywords
    _ra._expand_keywords = lambda n, w=kw_window: w
    state: PipelineState = {
        "creator_id": f"poc_{i}",
        "creator_niche": niche,
        "creator_profile": {},
        "research_output": None, "research_error": None,
        "scripting_output": None, "scripting_error": None,
        "visual_prompts": None, "visual_error": None,
    }
    try:
        result = research_agent(state)
    finally:
        _ra._expand_keywords = _original

    output = result.get("research_output") or {}
    topic_name = output.get("topic", "")
    print(f"  → topic: {topic_name}")
    if topic_name and topic_name not in seen:
        seen.add(topic_name)
        topics.append(topic_name)

print(f"\n\nFinal {len(topics)} distinct topics:")
for t in topics:
    print(f"  · {t}")
