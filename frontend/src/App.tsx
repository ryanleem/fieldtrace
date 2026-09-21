import {useEffect,useRef,useState} from 'react'
import {json,request,safeLink} from './api'
import type {Citation,Equipment,Photo,Replay,Result,Trace,Visual} from './types'

const labels=['front','back','left','right','top','bottom','nameplate','close_up','additional']
const emptyVisual:Visual={uploaded_images:[],aggregated_visual_findings:[],normalized_visual_findings:[]}
type Pending={key:string;file:File;url:string;view:string;note:string;ocr:boolean}
const demo=import.meta.env.VITE_DEMO_MODE==='true'
const emptyResult:Result={status:'not_run',message:'',primary_cause:null,alternative_causes:[],confidence:'LOW',recommended_actions:[],technical_claims:[],next_question:'',missing_information:[],sources:[],conflicts:[]}

function Badge({value}:{value:string}){return <span className={`badge ${value.toLowerCase()}`}>{value}</span>}
function SectionTitle({number,title,detail}:{number:string;title:string;detail?:string}){return <div className="section-heading"><span className="step-number">{number}</span><div><h2>{title}</h2>{detail&&<p>{detail}</p>}</div></div>}

export default function App(){
  const [sid,setSid]=useState(()=>demo?'':sessionStorage.getItem('fieldtrace.session')||'')
  const [equipment,setEquipment]=useState<Equipment|null>(null)
  const [visual,setVisual]=useState<Visual>(emptyVisual)
  const [trace,setTrace]=useState<Trace|null>(null)
  const [pending,setPending]=useState<Pending[]>([])
  const pendingRef=useRef(pending);pendingRef.current=pending
  const [model,setModel]=useState(''),[match,setMatch]=useState(''),[symptom,setSymptom]=useState(''),[followup,setFollowup]=useState('')
  const [entryType,setEntryType]=useState('answer')
  const [measurement,setMeasurement]=useState({name:'temperature',value:'',unit:'C',location:''})
  const [busy,setBusy]=useState(''),[error,setError]=useState(''),[notice,setNotice]=useState('')
  const [events,setEvents]=useState<string[]>([])
  const [source,setSource]=useState<Citation|null>(null),[sourceError,setSourceError]=useState(''),[sourceBusy,setSourceBusy]=useState(false)
  const sourceRequest=useRef(0),dialog=useRef<HTMLDialogElement>(null)
  const [replay,setReplay]=useState<Replay|null>(null)
  const confirmed=equipment?.confirmation_status==='CONFIRMED'
  const result=trace?.result||emptyResult
  const failed=result.status==='failed'
  const usable=result.status==='suspected_cause'&&!!result.primary_cause
  const photos=visual.uploaded_images.filter(i=>i.equipment_id===equipment?.confirmed_equipment_id)
  const findings=visual.aggregated_visual_findings.filter(f=>f.equipment_id===equipment?.confirmed_equipment_id)
  const newestRun=trace?.retrieved_evidence_history.at(-1)?.run_id
  const addEvent=(event:string)=>setEvents(old=>[...old,event])
  async function refresh(id=sid){
    if(!id||demo)return
    const [eq,v,t]=await Promise.all([request<Equipment>(`/sessions/${id}/equipment`),request<Visual>(`/sessions/${id}/visual-findings`),request<Trace>(`/sessions/${id}/troubleshooting`)])
    setEquipment(eq);setMatch(eq.confirmed_equipment_id||eq.ranked_candidates[0]?.candidate_id||'');setVisual(v);setTrace(t)
    return {eq,v,t}
  }
  async function work(label:string,operation:()=>Promise<void>){
    if(busy)return
    setBusy(label);setError('');setNotice('')
    try{await operation()}catch(e){setError(e instanceof Error?e.message:'The request failed. Your workspace is retained.')}finally{setBusy('')}
  }
  useEffect(()=>{if(sid&&!demo)void work('Restoring session…',async()=>{await refresh(sid)})},[]) // restored once; mutations refresh explicitly
  useEffect(()=>()=>{for(const p of pendingRef.current)URL.revokeObjectURL(p.url)},[])
  useEffect(()=>{if(source){dialog.current?.showModal()}else{dialog.current?.close()}},[!!source])
  function clearPending(){pending.forEach(p=>URL.revokeObjectURL(p.url));setPending([])}
  function start(){void work('Creating session…',async()=>{
    const eq=await request<Equipment>('/sessions',{method:'POST'})
    clearPending();setSid(eq.session_id);sessionStorage.setItem('fieldtrace.session',eq.session_id)
    setEquipment(eq);setTrace(null);setVisual(emptyVisual);setModel('');setMatch('');setSymptom('');setFollowup('');setEvents(['Session started']);setSource(null)
  })}
  function addFiles(files:FileList|null){
    if(!files)return
    const accepted=Array.from(files)
    if(accepted.some(f=>!['image/jpeg','image/png','image/webp'].includes(f.type)||f.size>10*1024*1024)){setError('Choose JPEG, PNG or WEBP images up to 10 MB each.');return}
    if(pending.length+visual.uploaded_images.length+accepted.length>30){setError('This prototype accepts up to 30 photos per session.');return}
    setPending(old=>[...old,...accepted.map(file=>({key:crypto.randomUUID(),file,url:URL.createObjectURL(file),view:'additional',note:'',ocr:false}))])
  }
  async function upload(){
    if(!pending.length)return
    const form=new FormData();pending.forEach(p=>form.append('images',p.file))
    form.append('view_labels',JSON.stringify(pending.map(p=>p.view)));form.append('user_notes',JSON.stringify(pending.map(p=>p.note||null)))
    const created=await request<Photo[]>(`/sessions/${sid}/images`,{method:'POST',body:form})
    clearPending();addEvent(`${created.length} photo${created.length===1?'':'s'} uploaded`);await refresh()
  }
  function identify(){void work('Reading nameplate and matching equipment…',async()=>{
    const selected=pending.filter(p=>p.ocr||p.view==='nameplate')
    if(selected.length>5)throw new Error('Select at most five photos for equipment identification.')
    if(!model.trim()&&!selected.length)throw new Error('Enter the model text or mark a nameplate photo for identification.')
    const form=new FormData();form.append('entered_equipment_text',model)
    selected.forEach(p=>form.append('images',p.file));form.append('image_roles',JSON.stringify(selected.map(p=>p.view==='nameplate'?'nameplate':'equipment')))
    const eq=await request<Equipment>(`/sessions/${sid}/equipment/identify`,{method:'POST',body:form})
    setEquipment(eq);setMatch(eq.ranked_candidates[0]?.candidate_id||'');setTrace(null);addEvent('Equipment identification updated; confirmation required')
    await refresh()
  })}
  function confirm(){void work('Confirming equipment and saving photos…',async()=>{
    const eq=await request<Equipment>(`/sessions/${sid}/equipment/confirm`,json({equipment_id:match,identification_revision:equipment?.identification_revision}))
    setEquipment(eq);setTrace(null);addEvent(`Equipment confirmed: ${eq.confirmed_model}`)
    await upload();await refresh()
  })}
  function analyze(){void work('Inspecting visible conditions…',async()=>{
    await upload()
    // analyze-all intentionally skips failed images; retry those explicitly.
    const current=await request<Photo[]>(`/sessions/${sid}/images`)
    for(const p of current.filter(p=>p.equipment_id===equipment?.confirmed_equipment_id&&['pending','failed'].includes(p.analysis_status))){
      await request(`/sessions/${sid}/images/${p.id}/analyze`,{method:'POST'})
    }
    const updated=await refresh();addEvent('Visible inspection results updated')
    if(updated?.v.uploaded_images.some(p=>p.equipment_id===updated.eq.confirmed_equipment_id&&p.analysis_status==='failed'))setError('Some photos could not be analyzed. They remain saved. Retry visible inspection when the service is available.')
  })}
  function run(){void work('Checking ABB documentation…',async()=>{
    if(symptom.trim()){setTrace(await request<Trace>(`/sessions/${sid}/troubleshooting/symptoms`,json({symptom})));addEvent(`Symptom added: ${symptom}`)}
    const t=await request<Trace>(`/sessions/${sid}/troubleshooting/run`,{method:'POST'})
    setTrace(t);addEvent(t.result.status==='failed'?'Troubleshooting service unavailable':'Troubleshooting result updated')
  })}
  function follow(){void work('Checking ABB documentation with your update…',async()=>{
    const input=entryType==='measurement'?{measurements:[measurement]}:entryType==='check'?{checks_completed:[followup]}:{answer:followup}
    if(trace)setTrace({...trace,result:{...emptyResult,status:'stale'}})
    const t=await request<Trace>(`/sessions/${sid}/troubleshooting/follow-up`,json({...input,expected_revision:trace?.revision}))
    setTrace(t);addEvent(`Follow-up: ${entryType==='measurement'?`${measurement.name} ${measurement.value} ${measurement.unit}`:followup}`)
    setFollowup('');setMeasurement({...measurement,value:''})
  })}
  async function openSource(citation:Citation){
    const serial=++sourceRequest.current;setSource(citation);setSourceError('');setSourceBusy(true)
    try{
      const data=demo?replay?.source_text[citation.chunk_id]:await request<Citation>(`/sessions/${sid}/troubleshooting/runs/${newestRun}/sources/${citation.chunk_id}`)
      if(serial===sourceRequest.current){if(!data?.chunk_text)throw new Error('The exact excerpt is unavailable. Use the stored manual link below.');setSource(data)}
    }catch(e){if(serial===sourceRequest.current)setSourceError(e instanceof Error?e.message:'Could not load source')}
    finally{if(serial===sourceRequest.current)setSourceBusy(false)}
  }
  function cites(ids:string[]=[]){return <div className="citations">{Array.from(new Set(ids)).map(id=>{const c=result.sources.find(s=>s.chunk_id===id);return c?<button className="source-chip" key={id} onClick={()=>void openSource(c)}>↗ {c.document_title}, p.{c.page_number}</button>:<span key={id}>Source unavailable</span>})}</div>}
  async function loadReplay(key:string){void work('Loading recorded example…',async()=>{
    const all=await fetch('/demo.json').then(r=>{if(!r.ok)throw new Error('Replay file is unavailable');return r.json()}) as Record<string,Replay>
    const saved=all[key];setReplay(saved);setEquipment(saved.equipment);setTrace(saved.trace);setVisual(saved.visual);setSid(saved.equipment.session_id);setSource(null)
    setEvents(['Prepared record loaded — replay, not a fresh analysis']);setSymptom(saved.trace.reported_symptoms.join('; '))
  })}
  const steps=[['01','Equipment',confirmed],['02','Visible evidence',photos.some(p=>['completed','no_clear_abnormality'].includes(p.analysis_status))],['03','Troubleshooting',usable],['04','Follow-up',!!trace?.follow_up_answers.length]] as const
  return <>
    <header className="topbar"><a className="brand" href="/" aria-label="FieldTrace home"><span className="brand-mark">F<span>↗</span></span><span>FieldTrace<small>MAINTENANCE INTELLIGENCE</small></span></a><div className="top-meta"><span className="prototype-label">ABB ACCELERATOR · PROTOTYPE</span><span className="live-dot"/>{demo?'RECORDED REPLAY':'LOCAL WORKSPACE'}</div></header>
    {demo&&<aside className="replay-banner"><strong>DEMO REPLAY · Not a fresh analysis</strong><span>Prepared records only. Live upload, OCR and model calls are disabled.</span><div>{['acs880','weak','visual'].map((k,i)=><button key={k} disabled={!!busy} onClick={()=>void loadReplay(k)}>{['ACS880 fault 5091','Low-evidence example','Recorded visible finding'][i]}</button>)}</div>{replay&&<p>{replay.disclosure}</p>}</aside>}
    <main>
      <section className="page-heading"><div><p className="eyebrow">TECHNICIAN WORKSPACE</p><h1>From observation<br className="mobile-break"/> to evidence.</h1><p>Identify the equipment. Capture the problem. Check the source.</p></div><button className="primary new-session" disabled={!!busy||demo} onClick={start}><span>＋</span> Start new troubleshooting session</button></section>
      <nav className="progress" aria-label="Troubleshooting steps">{steps.map(([n,title,done])=><div className={done?'done':''} key={n}><span>{done?'✓':n}</span>{title}</div>)}<span className="session-status">{sid?`Session ${sid.slice(0,8)} · ${confirmed?'Equipment confirmed':'Awaiting confirmation'}`:'No active session'}</span></nav>
      {error&&<div className="alert error" role="alert"><strong>Request not completed</strong><p>{error}</p>{sid&&!demo&&<button disabled={!!busy} onClick={()=>void work('Refreshing session…',async()=>{await refresh()})}>Refresh session status</button>}</div>}
      {notice&&<p role="status">{notice}</p>}
      {busy&&<div className="working" role="status"><span className="spinner"/>{busy}</div>}
      <div className="workspace">
        <div className="intake">
          <section className="panel"><SectionTitle number="01" title="Equipment & photos" detail="Start with the nameplate and a few clear views."/>
            <fieldset disabled={!sid||!!busy||demo}>
              <label className="upload-box"><span className="upload-symbol">＋</span><strong>Add equipment photos</strong><span>JPEG, PNG or WEBP · up to 10 MB each</span><input aria-label="Add equipment photos" type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={e=>{addFiles(e.target.files);e.target.value=''}}/></label>
              {pending.length>0&&<p className="hint">{confirmed?'Ready to upload.':'Photos are queued locally. Nameplate images can be read now; originals are saved against the equipment after you confirm it.'}</p>}
              <div className="photo-list">{pending.map(p=><article className="pending-photo" key={p.key}><img src={p.url} alt={p.file.name}/><div><strong title={p.file.name}>{p.file.name}</strong><label>View<select aria-label={`View for ${p.file.name}`} value={p.view} onChange={e=>setPending(old=>old.map(x=>x.key===p.key?{...x,view:e.target.value}:x))}>{labels.map(l=><option key={l} value={l}>{l.replace('_','-')}</option>)}</select></label><label>Photo note<input value={p.note} maxLength={1200} onChange={e=>setPending(old=>old.map(x=>x.key===p.key?{...x,note:e.target.value}:x))} placeholder="Optional observation"/></label><label className="checkbox"><input type="checkbox" checked={p.ocr||p.view==='nameplate'} onChange={e=>setPending(old=>old.map(x=>x.key===p.key?{...x,ocr:e.target.checked}:x))}/>Use for identification</label><button className="text-button" onClick={()=>{URL.revokeObjectURL(p.url);setPending(old=>old.filter(x=>x.key!==p.key))}}>Remove queued photo</button></div></article>)}</div>
              <label>Model text, if known<input value={model} onChange={e=>setModel(e.target.value)} placeholder="e.g. ABB ACS880-01" maxLength={1000}/></label>
              <button className="secondary full-width" onClick={identify}>{confirmed?'Re-detect / correct equipment':'Detect equipment / read nameplate'}</button>
            </fieldset>
            {equipment&&<div className="equipment-result"><div className="row"><p className="eyebrow">{confirmed?'CONFIRMED EQUIPMENT':'DETECTED EQUIPMENT'}</p>{equipment.confidence&&<Badge value={equipment.confidence}/>}</div><h3>{confirmed?equipment.confirmed_model:equipment.ranked_candidates[0]?.candidate_model||'No supported match yet'}</h3><p>{confirmed?equipment.confirmed_equipment_family:'Review the match before continuing.'}</p>{equipment.mismatch_warnings.map((w,i)=><p className="warning-note" key={i}>{w}</p>)}{!confirmed&&equipment.ranked_candidates.length>0&&<fieldset disabled={!!busy||demo}><label>Choose match<select value={match} onChange={e=>setMatch(e.target.value)}>{equipment.ranked_candidates.map(c=><option key={c.candidate_id} value={c.candidate_id}>{c.candidate_model} · {c.match_level}</option>)}</select></label><button className="primary full-width" disabled={!match} onClick={confirm}>Confirm equipment</button></fieldset>}{equipment.raw_ocr_text&&<details><summary>Read nameplate text</summary><pre>{equipment.raw_ocr_text}</pre></details>}</div>}
            {!sid&&<p className="hint">Start a session to add photos or identify equipment.</p>}
          </section>
          <section className="panel"><SectionTitle number="02" title="Visible findings" detail="Surface observations, not a diagnosis."/>
            {photos.length>0&&<div className="saved-photos">{photos.map(p=><figure key={p.id}><img src={demo?replay?.image_urls?.[p.id]:`/api/sessions/${sid}/images/${p.id}/file`} alt={p.original_filename}/><figcaption>{p.view_label.replace('_','-')}<small>{p.analysis_status.replaceAll('_',' ')}</small></figcaption>{p.user_note&&<p className="hint">Technician note: {p.user_note}</p>}</figure>)}</div>}
            {findings.map(f=><article className="finding" key={f.id}><span className="finding-marker"/><div><strong>{f.issue_type.replaceAll('_',' ')}</strong><p>{f.description}</p><small>Visual confidence: {f.visual_confidence.toUpperCase()} · {(f.supporting_image_ids||[f.image_id]).map(id=>photos.find(p=>p.id===id)?.view_label.replace('_','-')||'recorded image').join(', ')}</small></div></article>)}
            {!findings.length&&photos.length>0&&photos.every(p=>p.analysis_status==='no_clear_abnormality')?<p className="neutral-message">No obvious visible abnormality detected in these images.</p>:!findings.length&&<p className="empty-copy">{photos.some(p=>p.analysis_status==='failed')?'Image analysis is unavailable. No findings have been substituted.':'Uploaded photos will appear here with their visible observations.'}</p>}
            {photos.some(p=>p.analysis_status==='failed')&&<p className="warning-note">Some images failed analysis. Retry when the provider is available.</p>}
            {visual.uploaded_images.length>photos.length&&<p className="hint">Earlier photos belong to a different confirmation state and are not included. Upload fresh views for this equipment.</p>}
            <button className="secondary full-width" disabled={!confirmed||!!busy||demo||(!pending.length&&!photos.some(p=>['pending','failed'].includes(p.analysis_status)))} onClick={analyze}>Save photos & inspect visible conditions</button>
            {confirmed&&pending.length>0&&<button className="text-button full-width" disabled={!!busy||demo} onClick={()=>void work('Saving photos…',upload)}>Save photos without analysis</button>}
            {replay?.attribution&&<p className="hint">{replay.attribution}</p>}
          </section>
        </div>
        <div className="results-column">
          <section className="panel problem"><SectionTitle number="03" title="Describe the problem" detail="Use the exact fault code or the words you would use on site."/><fieldset disabled={!confirmed||!!busy||demo}><label>What problem are you seeing?<textarea value={symptom} maxLength={1200} onChange={e=>setSymptom(e.target.value)} placeholder="Drive shows fault 5091. Motor is overheating. There is an unusual noise." rows={3}/></label><div className="run-row"><small>{confirmed?'Confirmed equipment will scope the documentation search.':'Confirm equipment to continue.'}</small><button className="primary" disabled={!symptom.trim()&&!trace?.reported_symptoms.length} onClick={run}>Run troubleshooting <span>→</span></button></div></fieldset></section>
          <section className="panel result-panel" aria-label="Troubleshooting result"><div className="result-title"><p className="eyebrow">DOCUMENTED TROUBLESHOOTING</p>{!['not_run','stale'].includes(result.status)&&<Badge value={result.confidence}/>}</div>
            {failed?<div className="result-empty"><h2>Troubleshooting service unavailable</h2><p>Your session inputs are saved. No new diagnosis was generated. Try again when the service is available.</p><button disabled={!!busy||demo} onClick={()=>void work('Checking ABB documentation…',async()=>setTrace(await request<Trace>(`/sessions/${sid}/troubleshooting/run`,{method:'POST'})))}>Retry troubleshooting</button></div>:
            usable?<><p className="result-label">Primary suspected cause</p><h2 className="cause-title">{result.primary_cause!.label}</h2><p className="result-disclaimer">{result.message}</p><div className="rationale"><h3>Why</h3><p>{result.primary_cause!.rationale}</p>{cites(result.primary_cause!.citation_chunk_ids)}</div>
            {result.alternative_causes.length>0&&<div className="result-section"><h3>Other possible causes</h3>{result.alternative_causes.map((c,i)=><div key={i}><strong>{c.label}</strong><p>{c.rationale}</p>{cites(c.citation_chunk_ids)}</div>)}</div>}
            <div className="result-section"><h3>Recommended checks</h3>{result.recommended_actions.length?<ol className="checks">{result.recommended_actions.map((a,i)=><li key={i}><p>{a.action}</p>{cites(a.citation_chunk_ids)}</li>)}</ol>:<p className="empty-copy">No supported checks returned for this run.</p>}</div>
            {result.technical_claims.length>0&&<details className="claims"><summary>Technical statements & sources</summary>{result.technical_claims.map(c=><div key={c.claim_id}><p>{c.text}</p>{cites(c.citation_chunk_ids)}</div>)}</details>}</>:
            ['not_run','stale'].includes(result.status)?<div className="result-empty"><div className="document-symbol">≡</div><h2>{result.status==='stale'?'Session changed. Run troubleshooting again.':'A clearer next step starts with evidence.'}</h2><p>Confirmed equipment, visible observations and your symptom bring the relevant ABB documentation into this workspace.</p><div className="empty-tags"><span>Exact manual pages</span><span>Cited technical statements</span><span>Useful follow-up questions</span></div></div>:
            <div className="result-empty low-evidence"><span className="result-label">MORE EVIDENCE NEEDED</span><h2>We need more information before narrowing this down.</h2><p>{result.message}</p></div>}
            {result.conflicts.filter(c=>['CONFLICTING','DIFFERENT_APPLICABILITY'].includes(c.relationship)).map((c,i)=><aside className="conflict" key={i}><h3>Some source guidance differs.</h3><p>{c.relationship==='DIFFERENT_APPLICABILITY'?'These sources have different applicability. Confirm the model, revision and operating conditions.':'The backend flagged conflicting guidance. Review these sources before proceeding.'}</p>{cites(c.citation_chunk_ids)}</aside>)}
            {result.next_question&&!failed&&<aside className="next-question"><p className="eyebrow">NEXT QUESTION</p><h3>{result.next_question}</h3>{cites(result.question_sources)}</aside>}
            {sid&&trace&&result.status!=='not_run'&&<div className="follow-up"><SectionTitle number="04" title="Add more information" detail="Continue this session with an answer, measurement or completed check."/><fieldset disabled={!!busy||demo||!confirmed}><label>Entry type<select value={entryType} onChange={e=>setEntryType(e.target.value)}><option value="answer">Answer / observation / fault code</option><option value="check">Completed check</option><option value="measurement">Measurement</option></select></label>{entryType==='measurement'?<div className="measurement-grid">{(['name','value','unit','location'] as const).map(k=><label key={k}>{k}<input value={measurement[k]} onChange={e=>setMeasurement({...measurement,[k]:e.target.value})} maxLength={80}/></label>)}</div>:<label>Update for this session<textarea value={followup} maxLength={1200} onChange={e=>setFollowup(e.target.value)} placeholder="The cooling fan is running. Temperature is 92 C. I cleaned the vents and it is still overheating." rows={2}/></label>}<button className="secondary" disabled={entryType==='measurement'?(!measurement.name.trim()||!measurement.value.trim()):!followup.trim()} onClick={follow}>Submit update & check documentation →</button></fieldset></div>}
          </section>
          <section className="panel source-list"><div className="row"><h2>Sources</h2><span className="count">{result.sources.length}</span></div>{result.sources.length?result.sources.map(c=><button key={c.chunk_id} className="source-row" onClick={()=>void openSource(c)}><span className="page-icon">PDF</span><span><strong>{c.document_title}</strong><small>Page {c.page_number}{c.section_title?` · ${c.section_title}`:''}</small></span><span>↗</span></button>):<p className="empty-copy">Cited ABB manual pages will appear after a supported result.</p>}</section>
          <section className="panel history"><h2>Session activity</h2><ol>{events.map((e,i)=><li key={`local-${i}`}>{e}</li>)}{trace?.reported_symptoms.map((v,i)=><li key={`s${i}`}>Reported symptom: {v}</li>)}{trace?.follow_up_answers.map((v,i)=><li key={`f${i}`}>Follow-up saved: {v}</li>)}{trace?.checks_completed.map((v,i)=><li key={`c${i}`}>Completed check: {v}</li>)}{trace?.measurements.map((m,i)=><li key={`m${i}`}>Measurement: {m.name} {m.value} {m.unit} · {m.location}</li>)}{trace?.retrieved_evidence_history.map(r=><li key={r.run_id}>Documentation check · {r.status.replaceAll('_',' ')}<small>{new Date(r.created_at).toLocaleString()}</small></li>)}</ol>{!events.length&&!trace?.retrieved_evidence_history.length&&<p className="empty-copy">Equipment confirmation, checks and follow-ups are recorded here.</p>}{sid&&!demo&&<button className="text-button" disabled={!!busy} onClick={()=>void work('Refreshing session…',async()=>{await refresh()})}>Refresh saved session</button>}</section>
        </div>
      </div>
      <footer><span>FieldTrace <b>/</b> ABB Accelerator 2026</span><span>Prototype · Source-backed support for technician review</span></footer>
    </main>
    <dialog ref={dialog} onCancel={()=>{sourceRequest.current++;setSource(null)}} onClick={e=>{if(e.target===dialog.current){dialog.current.close();sourceRequest.current++;setSource(null)}}}><div className="source-dialog">{source&&<><div className="row"><p className="eyebrow">SOURCE EVIDENCE</p><button aria-label="Close source viewer" onClick={()=>{dialog.current?.close();sourceRequest.current++;setSource(null)}}>✕</button></div><h2>{source.document_title}</h2><p>Page {source.page_number}{source.section_title?` · ${source.section_title}`:''}</p><p className="hint">{source.document_number}{source.revision?` · Revision ${source.revision}`:''}</p>{sourceBusy?<p role="status">Loading exact cited excerpt…</p>:sourceError?<p role="alert">{sourceError}</p>:<><h3>Exact cited chunk</h3><pre className="excerpt">{source.chunk_text}</pre><p className="hint">Verbatim stored extraction. No highlights have been added.</p></>}{safeLink(source.citation_url||source.source_url)&&<a className="primary link-button" href={safeLink(source.citation_url||source.source_url)} target="_blank" rel="noopener noreferrer">Open manual page ↗</a>}{safeLink(source.source_url)&&<p className="source-url"><a href={safeLink(source.source_url)} target="_blank" rel="noopener noreferrer">{source.source_url}</a></p>}</>}</div></dialog>
  </>
}
