"""REFI-QDA Project export.

The official REFI-QDA Project is a .qdpx ZIP archive containing a project XML
file and a Sources directory.  This writer keeps the structure deliberately
small: project metadata, hierarchical codes, text sources and coded selections.
It is designed for interoperability and should be validated against the
current REFI-QDA XSD before claiming full conformance in a publication.
"""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from xml.etree.ElementTree import Element, SubElement, ElementTree, register_namespace
from uuid import uuid4
import json, shutil

NS='urn:QDA-XML:project:1.5'
register_namespace('', NS)

def q(tag): return f'{{{NS}}}{tag}'

def export_qdpx(project_dir, project, codes, sources, codings):
    out=Path(project_dir)/'exports'; out.mkdir(parents=True,exist_ok=True)
    qdpx=out/(project['title'].strip().replace(' ','_')[:60]+'_REFI-QDA.qdpx')
    root=Element(q('Project'))
    p=SubElement(root,q('Project')); p.set('name',project['title']); p.set('guid',str(uuid4())); p.set('creationDateTime',project.get('created_at',''))
    software=SubElement(p,q('Software')); software.set('name','ZedThema'); software.set('version','2.0')
    desc=SubElement(p,q('Description')); desc.text=project.get('description','')
    cb=SubElement(root,q('CodeBook')); codes_el=SubElement(cb,q('Codes'))
    by_parent={c.get('parent_id'):[] for c in codes}
    for c in codes: by_parent.setdefault(c.get('parent_id'),[]).append(c)
    def add_code(parent,c):
        el=SubElement(parent,q('Code'),{'guid':c['id'],'name':c['name'],'isCodable':str(not any(x.get('parent_id')==c['id'] for x in codes)).lower()})
        d=SubElement(el,q('Description')); d.text=c.get('definition','')
        for child in by_parent.get(c['id'],[]): add_code(el,child)
    for c in by_parent.get(None,[]): add_code(codes_el,c)
    src_el=SubElement(root,q('Sources'))
    source_lookup={s['id']:s for s in sources}
    for s in sources:
        ts=SubElement(src_el,q('TextSource'),{'guid':s['id'],'name':s['name'],'creationDateTime':s.get('created_at','')})
        text=json.loads(s['transcript']).get('segments',[]) if s.get('transcript') else []
        plain=' '.join(x.get('text','') for x in text)
        pc=SubElement(ts,q('PlainTextContent')); pc.text=plain
        sels=SubElement(ts,q('Selections'))
        offset=0
        for seg in text:
            segment_codings=[c for c in codings if c.get('source_id')==s['id'] and c.get('segment_id')==seg.get('id') and c.get('status')=='accepted']
            if not segment_codings: offset += len(seg.get('text',''))+1; continue
            sel=SubElement(sels,q('PlainTextSelection'),{'guid':str(uuid4()),'start':str(offset),'end':str(offset+len(seg.get('text','')))})
            for c in segment_codings: SubElement(sel,q('Coding'),{'guid':c['id'],'codeRef':c['code_id']})
            offset += len(seg.get('text',''))+1
    tree=ElementTree(root)
    xml_path=out/'project.qde'; tree.write(xml_path,encoding='utf-8',xml_declaration=True)
    with ZipFile(qdpx,'w',ZIP_DEFLATED) as z:
        z.write(xml_path,'project.qde')
        sources_dir=Path(project_dir)/'sources'
        if sources_dir.exists():
            for f in sources_dir.rglob('*'):
                if f.is_file(): z.write(f,'Sources/'+f.name)
    return qdpx

def export_qdc(project_dir, project, codes):
    """Export the codebook-only REFI-QDA Codebook (.qdc) format."""
    out=Path(project_dir)/'exports'; out.mkdir(parents=True,exist_ok=True)
    path=out/(project['title'].strip().replace(' ','_')[:60]+'_REFI-QDA.qdc')
    ns='urn:QDA-XML:codebook:1.0'; register_namespace('',ns)
    def tag(name): return f'{{{ns}}}{name}'
    root=Element(tag('CodeBook'))
    codes_el=SubElement(root,tag('Codes'))
    by_parent={None:[]}
    for c in codes: by_parent.setdefault(c.get('parent_id'),[]).append(c)
    def add(parent,c):
        children=by_parent.get(c['id'],[])
        el=SubElement(parent,tag('Code'),{'guid':c['id'],'name':c['name'],'isCodable':str(not children).lower()})
        desc=SubElement(el,tag('Description')); desc.text=c.get('definition','')
        for child in children: add(el,child)
    for c in by_parent.get(None,[]): add(codes_el,c)
    ElementTree(root).write(path,encoding='utf-8',xml_declaration=True)
    return path
