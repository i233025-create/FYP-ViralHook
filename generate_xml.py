"""
Run this once to generate a real Premiere Pro XML from mock scenes.
Output saved to: mock_export.xml
Usage: module1_style_extraction\venv\Scripts\python.exe generate_xml.py
"""
import sys
sys.path.insert(0, '.')

from pipeline.json_to_premiere_xml import build_xml, prettify_xml

# These match the mock script scenes in mockData.js (contrarian style)
scenes = [
    {
        "timecode": "0:00-0:03",
        "clip_idea": "Talking-head footage, direct eye contact",
        "caption": "AI WILL REPLACE DEVELOPERS?",
        "voiceover": "AI won't replace developers. But developers who use AI will replace those who don't."
    },
    {
        "timecode": "0:03-0:08",
        "clip_idea": "B-roll: news headlines montage",
        "caption": "WRONG QUESTION",
        "voiceover": "Everyone's debating whether AI takes our jobs. That's the wrong conversation entirely."
    },
    {
        "timecode": "0:08-0:15",
        "clip_idea": "B-roll: developer coding with AI assistant",
        "caption": "ONE-PERSON TEAM",
        "voiceover": "The real shift is this: AI agents are turning solo developers into one-person engineering teams."
    },
    {
        "timecode": "0:15-0:22",
        "clip_idea": "Screen: GitHub Copilot stats graphic",
        "caption": "55% MORE OUTPUT",
        "voiceover": "GitHub Copilot users ship 55% more code. Cursor users report finishing features in hours that used to take days."
    },
    {
        "timecode": "0:22-0:27",
        "clip_idea": "Return to talking head — confident close",
        "caption": "ARE YOU USING AI?",
        "voiceover": "The question isn't will AI replace you. It's — are you using AI yet?"
    },
]

root = build_xml(project_name="ViralHook_AI_Developers", scenes=scenes)
xml_str = prettify_xml(root)

with open("mock_export.xml", "w", encoding="utf-8") as f:
    f.write(xml_str)

print("✅ Written to mock_export.xml")
print(f"   Size: {len(xml_str)} chars")
