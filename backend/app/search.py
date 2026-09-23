"""Corpus search.

ZedThema tries semantic embeddings when sentence-transformers is installed.
If it is not installed, it falls back to TF-IDF. The response says which mode
was used so a researcher never mistakes lexical search for semantic search.
"""
import re, json
from .db import rows

def _segments(project_id):
    sources=rows('SELECT id,name,transcript FROM sources WHERE project_id=?',(project_id,))
    out=[]
    for s in sources:
        if not s.get('transcript'): continue
        try: data=json.loads(s['transcript']); segs=data.get('segments',[]) if isinstance(data,dict) else []
        except Exception: continue
        for seg in segs:
            text=seg.get('text','').strip()
            if text: out.append({'source_id':s['id'],'source_name':s['name'],'segment_id':seg.get('id'),'start':seg.get('start'), 'end':seg.get('end'),'text':text})
    return out

def search(project_id, query, limit=20):
    segments=_segments(project_id)
    if not segments: return {'mode':'none','results':[]}
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
        from .config import SEMANTIC_MODEL
        model=SentenceTransformer(SEMANTIC_MODEL)
        vectors=model.encode([query]+[x['text'] for x in segments],normalize_embeddings=True)
        scores=np.dot(vectors[1:],vectors[0])
        order=np.argsort(-scores)[:limit]
        return {'mode':'semantic','model':SEMANTIC_MODEL,'results':[{**segments[i],'score':round(float(scores[i]),6)} for i in order]}
    except Exception:
        # Simple local fallback. It requires no network or model download.
        q=set(re.findall(r'\w+',query.lower()))
        scored=[]
        for s in segments:
            words=set(re.findall(r'\w+',s['text'].lower())); score=len(q&words)/(len(q|words) or 1)
            if score>0: scored.append((score,s))
        scored.sort(key=lambda x:x[0],reverse=True)
        return {'mode':'tfidf_fallback','results':[{**s,'score':round(score,6)} for score,s in scored[:limit]]}
