"""Local LLM coding helpers.

The model receives the research context, codebook and transcript segments.  It
is explicitly told that quotations must be copied from the supplied text.
"""
import json, re, httpx
from .config import OLLAMA_URL, OLLAMA_MODEL

def _clean(s):
    s=re.sub(r'^```(?:json)?\s*','',s.strip(),flags=re.I); s=re.sub(r'\s*```$','',s); return s.strip()

def code_segments(segments,codes,project_context,model=None):
    model=model or OLLAMA_MODEL
    codebook=[{k:v for k,v in c.items() if k in ('name','definition','inclusion','exclusion','example','theory','parent_id')} for c in codes]
    prompt=f'''You are an expert qualitative researcher. Code evidence conservatively. Never invent quotations. Use only supplied transcript segments and codebook. A segment may receive zero, one, or multiple codes. Return ONLY valid JSON: {{"codings":[{{"segment_id":"...","code_name":"...","quote":"exact text from segment","confidence":0.0,"rationale":"brief evidence-based reason"}}]}}.
STUDY CONTEXT: {project_context}
CODEBOOK: {json.dumps(codebook,ensure_ascii=False)}
SEGMENTS: {json.dumps(segments,ensure_ascii=False)}'''
    r=httpx.post(f'{OLLAMA_URL}/api/generate',json={'model':model,'prompt':prompt,'stream':False,'format':'json','options':{'temperature':0}},timeout=600)
    r.raise_for_status(); data=json.loads(_clean(r.json().get('response','{}'))); return data.get('codings',[]),model

def dual_code(segments,codes,project_context,models):
    results=[]
    for model in models:
        items,used=code_segments(segments,codes,project_context,model)
        results.append({'model':used,'codings':items})
    return results
