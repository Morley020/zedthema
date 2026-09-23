from pathlib import Path
from zipfile import ZipFile
from app.refi import export_qdpx

def test_refi_qdpx_is_zip(tmp_path):
    project={'title':'Test Project','description':'Test','created_at':'2026-01-01T00:00:00Z'}
    codes=[{'id':'c1','name':'Trust','parent_id':None,'definition':'Confidence'}]
    sources=[{'id':'s1','name':'Interview 1','created_at':'2026-01-01T00:00:00Z','transcript':'{"segments":[{"id":"seg_0001","text":"I trust the service."}]}'}]
    codings=[{'id':'x1','source_id':'s1','segment_id':'seg_0001','code_id':'c1','status':'accepted'}]
    out=export_qdpx(tmp_path,project,codes,sources,codings)
    assert out.exists()
    with ZipFile(out) as z:
        assert 'project.qde' in z.namelist()
        xml=z.read('project.qde')
        assert b'Trust' in xml
