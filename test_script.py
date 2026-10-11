import sys, traceback
sys.path.insert(0, '.')

from pipeline.agents.scripting_agent import (
    _load_creator_profile, _load_chroma_retriever,
    _retrieve_examples, _extract_style_params, generate_no_history
)
from langchain_groq import ChatGroq
import os
from dotenv import load_dotenv

load_dotenv('module1_style_extraction/.env')

profile = _load_creator_profile()
print('profile loaded:', bool(profile))

style_params = _extract_style_params(profile)
print('style_params:', style_params)

api_key = os.getenv('GROQ_API_KEY', '')
print('api_key set:', bool(api_key))

llm = ChatGroq(api_key=api_key, model_name='llama-3.3-70b-versatile', temperature=0.7, max_tokens=2048)

try:
    script, meta = generate_no_history('Morning routine productivity tips', style_params, llm)
    print('SUCCESS')
    print('concept:', script.concept_name)
    print('hook_type:', script.hook_type)
    print('scenes:', len(script.scenes))
except Exception as e:
    traceback.print_exc()
