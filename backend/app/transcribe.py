from pathlib import Path
from functools import lru_cache

@lru_cache(maxsize=3)
def get_model(name):
    from faster_whisper import WhisperModel
    return WhisperModel(name, device='cpu', compute_type='int8')

def transcribe(path, model_name='small', language='auto'):
    model=get_model(model_name)
    lang=None if language in ('auto','') else language
    segments,info=model.transcribe(str(path),language=lang,beam_size=5,vad_filter=True,word_timestamps=False)
    rows=[]
    for i,s in enumerate(segments):
        text=s.text.strip()
        if text: rows.append({'id':f'seg_{i+1:04d}','start':round(s.start,2),'end':round(s.end,2),'text':text})
    return {'segments':rows,'language':getattr(info,'language',language),'duration':getattr(info,'duration',None)}
