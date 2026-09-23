"""Optional speaker diarization using pyannote.audio.

pyannote is intentionally optional because its model is large and may require
Hugging Face access.  The rest of ZedThema works without it.
"""
from .config import HF_TOKEN, DIARIZATION_MODEL

def diarize(path):
    try:
        from pyannote.audio import Pipeline
    except ImportError as exc:
        raise RuntimeError("Speaker diarization is optional. Install the diarization extra first: pip install -r requirements-diarization.txt") from exc
    if not HF_TOKEN:
        raise RuntimeError("HF_TOKEN is required for the configured pyannote model. Add it to backend/.env if your model requires authentication.")
    pipeline=Pipeline.from_pretrained(DIARIZATION_MODEL, use_auth_token=HF_TOKEN)
    diarization=pipeline(path)
    turns=[]
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        turns.append({'start':round(float(turn.start),3),'end':round(float(turn.end),3),'speaker':speaker})
    return {'model':DIARIZATION_MODEL,'turns':turns}

def attach_speakers(transcript, turns):
    """Attach the speaker with the greatest time overlap to each transcript segment."""
    for seg in transcript.get('segments',[]):
        best=None; best_overlap=0.0
        for t in turns:
            overlap=max(0.0,min(seg['end'],t['end'])-max(seg['start'],t['start']))
            if overlap>best_overlap: best_overlap=overlap; best=t['speaker']
        seg['speaker']=best or 'UNKNOWN'
    return transcript
