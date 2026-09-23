import React, {useEffect, useMemo, useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';

// The API URL can be changed at build time with VITE_API_URL.
const API = import.meta.env.VITE_API_URL || 'http' + ':' + '/' + '/' + '127.0.0.1' + ':' + '8000' + '/api';

async function api(url, options={}) {
  const token = localStorage.getItem('qualicoder_token');
  const headers = new Headers(options.headers || {});
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const response = await fetch(API + url, {...options, headers});
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || 'Request failed');
  return data;
}

const emptyCode = {name:'', definition:'', inclusion:'', exclusion:'', example:'', theory:'', parent_id:''};

function App(){
  const [health,setHealth]=useState(null), [loggedIn,setLoggedIn]=useState(Boolean(localStorage.getItem('qualicoder_token')));
  const [authMode,setAuthMode]=useState('login');
  const [projects,setProjects]=useState([]), [pid,setPid]=useState(''), [p,setP]=useState(null);
  const [tab,setTab]=useState('study'), [busy,setBusy]=useState(false), [err,setErr]=useState(''), [models,setModels]=useState([]);
  const [form,setForm]=useState({title:'',description:'',research_question:'',framework:'',method:'Thematic analysis',languages:['en']});
  const [code,setCode]=useState(emptyCode); const [editing,setEditing]=useState(null);
  const [url,setUrl]=useState(''), [path,setPath]=useState(''), [search,setSearch]=useState(''), [searchResults,setSearchResults]=useState(null);
  const [dualModels,setDualModels]=useState(['','']); const [agreement,setAgreement]=useState(null);

  const load=async()=>{
    try {
      const h=await api('/health'); setHealth(h);
      if(h.auth_enabled && !localStorage.getItem('qualicoder_token')) return;
      setProjects(await api('/projects'));
      setModels((await api('/models')).models||[]);
    } catch(e){setErr(e.message)}
  };
  useEffect(()=>{load()},[loggedIn]);
  useEffect(()=>{if(pid) api('/projects/'+pid).then(setP).catch(e=>setErr(e.message)); else setP(null)},[pid]);
  if(health?.auth_enabled && !loggedIn) return <Login mode={authMode} setMode={setAuthMode} onLogin={()=>setLoggedIn(true)}/>;

  const create=async()=>{setBusy(true);try{const x=await api('/projects',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(form)});await load();setPid(x.id);setTab('codebook')}catch(e){setErr(e.message)}finally{setBusy(false)}};
  const addCode=async()=>{if(!code.name.trim())return;setBusy(true);try{await api(`/projects/${pid}/codes`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...code,parent_id:code.parent_id||null})});setCode(emptyCode);await refresh()}catch(e){setErr(e.message)}finally{setBusy(false)}};
  const refresh=async()=>setP(await api('/projects/'+pid));
  const upload=async e=>{const f=e.target.files[0];if(!f)return;const fd=new FormData();fd.append('file',f);setBusy(true);try{await api(`/projects/${pid}/sources/upload?language=${form.languages[0]||'auto'}`,{method:'POST',body:fd});await refresh()}catch(e){setErr(e.message)}finally{setBusy(false)}};
  const addUrl=async()=>{setBusy(true);try{await api(`/projects/${pid}/source-url`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url,language:'auto'})});setUrl('');await refresh()}catch(e){setErr(e.message)}finally{setBusy(false)}};
  const addPath=async()=>{setBusy(true);try{await api(`/projects/${pid}/source-path`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path,language:'auto'})});setPath('');await refresh()}catch(e){setErr(e.message)}finally{setBusy(false)}};
  const transcribe=async s=>{setBusy(true);try{await api(`/projects/${pid}/sources/${s.id}/transcribe?model=small&language=${s.language||'auto'}`,{method:'POST'});await refresh()}catch(e){setErr(e.message)}finally{setBusy(false)}};
  const diarizeSource=async s=>{setBusy(true);try{await api(`/projects/${pid}/sources/${s.id}/diarize`,{method:'POST'});await refresh()}catch(e){setErr(e.message)}finally{setBusy(false)}};
  const codeIt=async s=>{setBusy(true);try{await api(`/projects/${pid}/sources/${s.id}/code`,{method:'POST'});setTab('review');}catch(e){setErr(e.message)}finally{setBusy(false)}};
  const doSearch=async()=>{if(!search.trim())return;setSearchResults(await api(`/projects/${pid}/search`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:search,limit:30})}))};
  const dualCode=async s=>{const ms=dualModels.filter(Boolean);if(ms.length!==2){setErr('Choose two Ollama models first.');return}setBusy(true);try{const result=await api(`/projects/${pid}/sources/${s.id}/dual-code`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({models:ms})});setAgreement(await api('/compare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({a:result[0].codings,b:result[1].codings})}));setTab('agreement')}catch(e){setErr(e.message)}finally{setBusy(false)}};

  if(!p) return <Shell projects={projects} pid={pid} setPid={setPid} health={health} setPidNew={()=>setPid('')}><NewProject form={form} setForm={setForm} create={create} busy={busy}/></Shell>;

  const tabs=[['study','Study'],['codebook','Codebook'],['sources','Sources'],['search','Corpus search'],['review','Human review'],['agreement','Agreement'],['anomalies','Quantitative links'],['audit','Audit trail']];
  return <Shell projects={projects} pid={pid} setPid={setPid} health={health} setPidNew={()=>setPid('')}>
    <header className="pagehead"><div><span className="eyebrow">QUALITATIVE RESEARCH WORKSPACE</span><h2>{p.title}</h2></div><div className="head-actions"><span className="status">{busy?'Processing…':'Ready'}</span><button onClick={async()=>{try{const x=await api(`/projects/${pid}/export`,{method:'POST'});alert('Exported: '+x.files.join(', '))}catch(e){setErr(e.message)}}}>Export package</button></div></header>
    {err&&<div className="error" onClick={()=>setErr('')}>{err} <span>×</span></div>}
    <nav className="tabs">{tabs.map(([k,v])=><button className={tab===k?'active':''} onClick={()=>setTab(k)} key={k}>{v}</button>)}</nav>
    {tab==='study'&&<Study p={p} models={models}/>} 
    {tab==='codebook'&&<Codebook p={p} code={code} setCode={setCode} addCode={addCode} editing={editing} setEditing={setEditing} refresh={refresh}/>} 
    {tab==='sources'&&<Sources p={p} upload={upload} url={url} setUrl={setUrl} addUrl={addUrl} path={path} setPath={setPath} addPath={addPath} transcribe={transcribe} diarize={diarizeSource} codeIt={codeIt} dualCode={dualCode} models={models} dualModels={dualModels} setDualModels={setDualModels}/>} 
    {tab==='search'&&<Search search={search} setSearch={setSearch} doSearch={doSearch} results={searchResults}/>} 
    {tab==='review'&&<Review pid={pid}/>} 
    {tab==='agreement'&&<Agreement result={agreement}/>} 
    {tab==='anomalies'&&<Anomalies pid={pid}/>} 
    {tab==='audit'&&<Audit pid={pid}/>} 
  </Shell>;
}

function Login({mode,setMode,onLogin}){
  const [email,setEmail]=useState(''); const [password,setPassword]=useState(''); const [displayName,setDisplayName]=useState(''); const [error,setError]=useState('');
  const submit=async()=>{try{const endpoint=mode==='login'?'/auth/login':'/auth/register';const body=mode==='login'?{email,password}:{email,password,display_name:displayName};const r=await api(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});localStorage.setItem('qualicoder_token',r.token);onLogin()}catch(e){setError(e.message)}};
  return <div className="auth-page"><div className="card auth-card"><h1>ZedThema</h1><p className="muted">Research workspace sign-in</p>{mode==='register'&&<Field label="Display name"><input value={displayName} onChange={e=>setDisplayName(e.target.value)}/></Field>}<Field label="Email"><input type="email" value={email} onChange={e=>setEmail(e.target.value)}/></Field><Field label="Password"><input type="password" value={password} onChange={e=>setPassword(e.target.value)}/></Field>{error&&<div className="error">{error}</div>}<button className="primary wide" onClick={submit}>{mode==='login'?'Sign in':'Create account'}</button><button className="linkbtn" onClick={()=>setMode(mode==='login'?'register':'login')}>{mode==='login'?'Need an account? Register':'Already registered? Sign in'}</button></div></div>
}

function Shell({children,projects,pid,setPid,health,setPidNew}){return <div className="app"><aside><div><h1>ZedThema</h1><p className="side-sub">Open-source AI-assisted qualitative research</p><button className="primary wide" onClick={setPidNew}>+ New project</button><h3>Projects</h3>{projects.map(x=><button className={'project '+(x.id===pid?'sel':'')} onClick={()=>setPid(x.id)} key={x.id}>{x.title}</button>)}</div><div className="sidefoot">{health?.auth_enabled&&<button className="logout" onClick={()=>{localStorage.removeItem('qualicoder_token');location.reload()}}>Sign out</button>}<span className={health?.ollama?'dot ok':'dot'}></span> Ollama {health?.ollama?'connected':'not detected'}<br/>Local-first · Human review<br/>Encryption-ready · Audit trail</div></aside><main>{children}</main></div>}

function NewProject({form,setForm,create,busy}){return <section className="card form"><h3>Study design</h3><p className="muted">Define the study before importing evidence. ZedThema does not assume a particular theory or research method.</p><Field label="Project title"><input value={form.title} onChange={e=>setForm({...form,title:e.target.value})} placeholder="e.g. Digital health adoption in Zambia"/></Field><Field label="Research question"><textarea value={form.research_question} onChange={e=>setForm({...form,research_question:e.target.value})}/></Field><Field label="Theoretical framework"><input value={form.framework} onChange={e=>setForm({...form,framework:e.target.value})} placeholder="UTAUT2, TOE, DOI, STS, inductive…"/></Field><Field label="Method"><input value={form.method} onChange={e=>setForm({...form,method:e.target.value})}/></Field><button className="primary" disabled={busy||!form.title.trim()} onClick={create}>Create project</button></section>}
function Field({label,children}){return <label><span>{label}</span>{children}</label>}
function Study({p,models}){return <section className="grid"><div className="card"><h3>Study design</h3><Info label="Question" value={p.research_question}/><Info label="Framework" value={p.framework}/><Info label="Method" value={p.method}/><Info label="Languages" value={p.languages?.join(', ')}/></div><div className="card"><h3>Local AI</h3><p>Ollama models detected: <b>{models.length}</b></p>{models.map(m=><div className="model" key={m.name}>{m.name}</div>)}<p className="note">AI outputs are provisional. A researcher must validate codes and quotations before treating them as findings.</p></div></section>}
function Info({label,value}){return <p><b>{label}</b><br/>{value||'—'}</p>}

function Codebook({p,code,setCode,addCode,editing,setEditing,refresh}){const tree=useMemo(()=>{const by={};p.codes.forEach(c=>{by[c.id]=[]});p.codes.forEach(c=>{if(c.parent_id&&by[c.parent_id])by[c.parent_id].push(c)});return p.codes.filter(c=>!c.parent_id).map(c=>({...c,children:build(c.id,by)}));function build(id,b){return (b[id]||[]).map(c=>({...c,children:build(c.id,b)}))}},[p.codes]);return <section className="grid"><div className="card"><h3>{editing?'Edit code':'Add code'}</h3>{['name','definition','inclusion','exclusion','example','theory'].map(k=><Field label={k} key={k}><input value={code[k]||''} onChange={e=>setCode({...code,[k]:e.target.value})}/></Field>)}<Field label="Parent code"><select value={code.parent_id||''} onChange={e=>setCode({...code,parent_id:e.target.value})}><option value="">No parent (top level)</option>{p.codes.filter(c=>!editing||c.id!==editing).map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></Field><div className="row"><button className="primary" onClick={async()=>{if(editing){await api(`/projects/${p.id}/codes/${editing}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({...code,parent_id:code.parent_id||null})});setEditing(null);setCode({name:'',definition:'',inclusion:'',exclusion:'',example:'',theory:'',parent_id:''});await refresh()}else addCode()}}>{editing?'Save changes':'Add to codebook'}</button>{editing&&<button onClick={()=>{setEditing(null);setCode(emptyCode)}}>Cancel</button>}</div></div><div className="card"><h3>Hierarchical codebook</h3>{tree.length?<CodeTree nodes={tree} onEdit={c=>{setEditing(c.id);setCode({...c,parent_id:c.parent_id||''})}}/>:<p className="muted">No codes yet.</p>}</div></section>}
function CodeTree({nodes,onEdit,depth=0}){return nodes.map(c=><div key={c.id} className="tree" style={{marginLeft:depth*18}}><div className="tree-row"><div><b>{c.name}</b><small>{c.definition||'No definition'}</small></div><button onClick={()=>onEdit(c)}>Edit</button></div>{c.children?.length>0&&<CodeTree nodes={c.children} onEdit={onEdit} depth={depth+1}/>}</div>)}

function Sources({p,upload,url,setUrl,addUrl,path,setPath,addPath,transcribe,diarize,codeIt,dualCode,models,dualModels,setDualModels}){return <section><div className="card"><h3>Source data</h3><div className="sourcegrid"><div><b>Upload file</b><p className="muted">Audio, video, TXT, DOCX, PDF, CSV, JSON</p><input type="file" onChange={upload}/></div><div><b>Public URL</b><input value={url} onChange={e=>setUrl(e.target.value)} placeholder="https://…"/><button onClick={addUrl}>Import URL</button></div><div><b>Local path</b><input value={path} onChange={e=>setPath(e.target.value)} placeholder="/Users/.../interview.m4a"/><button onClick={addPath}>Import path</button></div></div></div><div className="card"><h3>Corpus</h3>{p.sources.length===0?<p className="muted">No sources yet.</p>:p.sources.map(s=><SourceRow key={s.id} s={s} transcribe={transcribe} diarize={diarize} codeIt={codeIt} dualCode={dualCode} models={models} dualModels={dualModels} setDualModels={setDualModels}/>)}</div></section>}
function SourceRow({s,transcribe,diarize,codeIt,dualCode,models,dualModels,setDualModels}){const[segments,setSegments]=useState([]);const show=async()=>setSegments(await api(`/projects/${s.project_id}/sources/${s.id}/segments`));return <div className="source"><div className="source-main"><b>{s.name}</b><small>{s.source_type} · {s.language}</small>{segments.length>0&&<div className="segments">{segments.map(x=><div className="segment" key={x.id}><span>{fmt(x.start)}–{fmt(x.end)} {x.speaker&&<b>{x.speaker}</b>}</span><p>{x.text}</p></div>)}</div>}</div><div className="actions"><button onClick={()=>transcribe(s)}>Transcribe</button>{s.source_type==='audio'||s.source_type==='video'?<button onClick={()=>diarize(s)}>Diarize</button>:null}<button onClick={show}>Segments</button><button className="primary" onClick={()=>codeIt(s)}>AI code</button><select value={dualModels[0]} onChange={e=>setDualModels([e.target.value,dualModels[1]])}><option value="">Model A</option>{models.map(m=><option key={m.name} value={m.name}>{m.name}</option>)}</select><select value={dualModels[1]} onChange={e=>setDualModels([dualModels[0],e.target.value])}><option value="">Model B</option>{models.map(m=><option key={m.name} value={m.name}>{m.name}</option>)}</select><button onClick={()=>dualCode(s)}>Compare</button></div></div>}
function fmt(v){if(v===undefined||v===null)return '—';const sec=Math.floor(v);return `${String(Math.floor(sec/60)).padStart(2,'0')}:${String(sec%60).padStart(2,'0')}`}

function Search({search,setSearch,doSearch,results}){return <section className="card"><h3>Corpus search</h3><p className="muted">Semantic embeddings are used when the optional embedding package is installed. Otherwise ZedThema clearly labels the local fallback search.</p><div className="searchbar"><input value={search} onChange={e=>setSearch(e.target.value)} onKeyDown={e=>e.key==='Enter'&&doSearch()} placeholder="e.g. concerns about driver safety"/><button className="primary" onClick={doSearch}>Search</button></div>{results&&<><p className="badge">Mode: {results.mode}{results.model?` · ${results.model}`:''}</p>{results.results.map((r,i)=><div className="result" key={i}><div><b>{r.source_name}</b><small>{fmt(r.start)}–{fmt(r.end)} · score {r.score}</small></div><p>“{r.text}”</p></div>)}</>}</section>}

function Review({pid}){const[x,setX]=useState([]);const[editing,setEditing]=useState(null);const load=()=>api(`/projects/${pid}/codings`).then(setX);useEffect(load,[pid]);const update=async(c,status)=>{await api('/codings/'+c.id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status,...(editing?.id===c.id?editing.fields:{})})});setEditing(null);load()};return <section className="card"><h3>Human validation</h3><p className="muted">Accept, reject, or edit each AI suggestion. Accepted coding is the evidence that should feed your final analysis.</p>{x.map(c=><div className="coding" key={c.id}><div><div className="quote">“{c.quote}”</div><small>{c.source_name} · {fmt(c.start)}–{fmt(c.end)} · {c.model}</small></div><div><b>{c.code_name}</b> <span className="confidence">{Math.round(c.confidence*100)}%</span><p>{c.rationale}</p></div><div className="actions"><button onClick={()=>update(c,'accepted')}>Accept</button><button onClick={()=>setEditing({id:c.id,fields:{code_name:c.code_name,rationale:c.rationale}})}>Edit</button><button onClick={()=>update(c,'rejected')}>Reject</button></div>{editing?.id===c.id&&<div className="editbox"><input value={editing.fields.code_name} onChange={e=>setEditing({...editing,fields:{...editing.fields,code_name:e.target.value}})}/><textarea value={editing.fields.rationale} onChange={e=>setEditing({...editing,fields:{...editing.fields,rationale:e.target.value}})}/><button className="primary" onClick={()=>update(c,'edited')}>Save review</button></div>}</div>)}</section>}

function Agreement({result}){return <section className="card"><h3>Dual-model agreement</h3>{result?<div className="metrics"><Metric label="Jaccard" value={result.jaccard}/><Metric label="Cohen's kappa" value={result.cohen_kappa?.kappa}/><Metric label="Krippendorff alpha" value={result.krippendorff_alpha_nominal?.alpha}/><Metric label="Units" value={result.cohen_kappa?.units}/></div>:<p className="muted">Run Compare from a source to calculate agreement between two models.</p>}<p className="note">Agreement is evidence about consistency, not proof that a code is substantively correct. Human validation remains part of the workflow.</p></section>}
function Metric({label,value}){return <div className="metric"><small>{label}</small><strong>{value??'—'}</strong></div>}

function Anomalies({pid}){const[f,setF]=useState({label:'',description:'',metric:'',value:'',context:''});const[x,setX]=useState([]);const load=()=>api(`/projects/${pid}`).then(a=>setX(a.anomalies));useEffect(load,[pid]);return <section className="grid"><div className="card"><h3>Link quantitative findings</h3>{Object.keys(f).map(k=><Field label={k} key={k}><input value={f[k]} onChange={e=>setF({...f,[k]:e.target.value})}/></Field>)}<button className="primary" onClick={async()=>{await api(`/projects/${pid}/anomalies`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(f)});setF({label:'',description:'',metric:'',value:'',context:''});load()}}>Save anomaly</button></div><div className="card"><h3>Recorded anomalies</h3>{x.map(a=><div className="code" key={a.id}><b>{a.label}</b><p>{a.description}</p><small>{a.metric} {a.value}</small></div>)}</div></section>}
function Audit({pid}){const[x,setX]=useState([]);useEffect(()=>{api(`/projects/${pid}/audit`).then(setX)},[pid]);return <section className="card"><h3>Reproducibility audit</h3>{x.map(a=><div className="audit" key={a.id}><b>{a.event}</b><small>{a.created_at}</small><pre>{a.details}</pre></div>)}</section>}

createRoot(document.getElementById('root')).render(<App/>);
