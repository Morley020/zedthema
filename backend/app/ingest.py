"""Safe source ingestion helpers."""
from pathlib import Path
import ipaddress, json, shutil, socket, uuid, urllib.parse
import httpx
from docx import Document
from pypdf import PdfReader
import pandas as pd
from .config import DATA_DIR, MAX_SOURCE_MB

AUDIO={'.mp3','.m4a','.wav','.aac','.flac','.ogg','.wma'}
VIDEO={'.mp4','.mov','.mkv','.avi','.webm'}
TEXT={'.txt','.md','.rtf','.docx','.pdf','.csv','.json'}

def extract_text(path: Path):
    ext=path.suffix.lower()
    if ext in {'.txt','.md','.rtf'}: return path.read_text(encoding='utf-8',errors='ignore')
    if ext=='.docx': return '\n'.join(p.text for p in Document(path).paragraphs)
    if ext=='.pdf': return '\n'.join((p.extract_text() or '') for p in PdfReader(path).pages)
    if ext=='.csv': return pd.read_csv(path).to_csv(index=False)
    if ext=='.json': return json.dumps(json.loads(path.read_text(encoding='utf-8')),ensure_ascii=False,indent=2)
    return None

def save_upload(project_id, filename, fileobj):
    dest=DATA_DIR/'projects'/project_id/'sources'; dest.mkdir(parents=True,exist_ok=True)
    safe=Path(filename).name or 'source.bin'; out=dest/f"{uuid.uuid4().hex[:10]}_{safe}"
    total=0
    try:
        with out.open('wb') as f:
            while True:
                chunk=fileobj.read(1024*1024)
                if not chunk: break
                total += len(chunk)
                if total>MAX_SOURCE_MB*1024*1024:
                    raise ValueError(f'File exceeds MAX_SOURCE_MB ({MAX_SOURCE_MB} MB)')
                f.write(chunk)
    except Exception:
        out.unlink(missing_ok=True); raise
    return out

def copy_local(project_id, raw_path):
    p=Path(raw_path).expanduser().resolve()
    if not p.is_file(): raise FileNotFoundError(str(p))
    with p.open('rb') as source: return save_upload(project_id,p.name,source)

def _reject_private_host(hostname):
    """Prevent a public URL import from silently becoming an SSRF primitive."""
    try:
        addresses={x[4][0] for x in socket.getaddrinfo(hostname,None)}
    except socket.gaierror as exc:
        raise ValueError(f'Could not resolve host: {hostname}') from exc
    for addr in addresses:
        ip=ipaddress.ip_address(addr)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError('URL points to a private/reserved network address. Use a local path for local files.')

async def download_url(project_id,url):
    parsed=urllib.parse.urlparse(url)
    if parsed.scheme not in {'http','https'}: raise ValueError('Only HTTP/HTTPS URLs are allowed.')
    if not parsed.hostname: raise ValueError('URL has no hostname.')
    _reject_private_host(parsed.hostname)
    name=Path(parsed.path).name or 'downloaded_source'
    async with httpx.AsyncClient(follow_redirects=True,timeout=120) as client:
        async with client.stream('GET',url) as r:
            r.raise_for_status()
            content_length=int(r.headers.get('content-length','0') or 0)
            if content_length and content_length>MAX_SOURCE_MB*1024*1024: raise ValueError(f'URL response exceeds MAX_SOURCE_MB ({MAX_SOURCE_MB} MB)')
            class Stream:
                def __init__(self, response): self.response=response; self.total=0
                def read(self,n=-1):
                    raise RuntimeError('stream wrapper should be consumed by iter_bytes')
            # Save the response incrementally so a large URL does not consume RAM.
            dest=DATA_DIR/'projects'/project_id/'sources'; dest.mkdir(parents=True,exist_ok=True)
            out=dest/f"{uuid.uuid4().hex[:10]}_{Path(name).name}"
            total=0
            try:
                with out.open('wb') as f:
                    async for chunk in r.aiter_bytes(1024*1024):
                        total += len(chunk)
                        if total>MAX_SOURCE_MB*1024*1024: raise ValueError(f'URL response exceeds MAX_SOURCE_MB ({MAX_SOURCE_MB} MB)')
                        f.write(chunk)
            except Exception:
                out.unlink(missing_ok=True); raise
    return out

def type_for(path):
    e=path.suffix.lower()
    if e in AUDIO:return 'audio'
    if e in VIDEO:return 'video'
    if e in TEXT:return 'text'
    return 'file'
