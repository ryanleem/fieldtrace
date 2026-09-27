import {normalizeEquipment,normalizeTrace,normalizeVisual} from './sessionData'
import {useEffect,useRef,useState,type ReactNode} from 'react'
import {json,request,safeLink} from './api'
import PrivatePhoto from './PrivatePhoto'
import RemovePhotoDialog from './RemovePhotoDialog'
import NameDialog from './NameDialog'
import useSessionSave,{type Draft} from './useSessionSave'
import DeleteSessionDialog from './DeleteSessionDialog'
import type {Citation,Equipment,Photo,Replay,Result,Trace,Visual,SessionMeta} from './types'

const labels=['front','back','left','right','top','bottom','nameplate','close_up','additional']
const emptyVisual:Visual={uploaded_images:[],aggregated_visual_findings:[],normalized_visual_findings:[]}
type Pending={key:string;fingerprint:string;file:File;url:string;view:string;note:string;ocr:boolean;saveError?:string}
const emptyResult:Result={status:'not_run',message:'',primary_cause:null,alternative_causes:[],confidence:'LOW',recommended_actions:[],technical_claims:[],next_question:'',missing_information:[],sources:[],conflicts:[]}

function Badge({value}:{value:string}){return <span className={`badge ${value.toLowerCase()}`}>{value}</span>}
function SectionTitle({number,title,detail}:{number:string;title:string;detail?:string}){return <div className="section-heading"><span className="step-number">{number}</span><div><h2>{title}</h2>{detail&&<p>{detail}</p>}</div></div>}

export default function App({userId,demo=false,account,initialPage='workspace',onSessionOperation}:{userId:string;demo?:boolean;account?:ReactNode;initialPage?:'workspace'|'history';onSessionOperation?:(operation:'create'|'reopen')=>void}){
  const storageKey=`fieldtrace.session.${userId}`
  const [sessionName,setSessionName]=useState(''),[page,setPage]=useState<'workspace'|'history'>(initialPage)
  const [history,setHistory]=useState<SessionMeta[]>([]),[hasMore,setHasMore]=useState(false)
  const [namePrompt,setNamePrompt]=useState<{initial:string;rename:boolean}|null>(null)
  const [deletePrompt,setDeletePrompt]=useState<SessionMeta|null>(null)
  const deleteResolver=useRef<((confirmed:boolean)=>void)|null>(null)
  function resolveDelete(value:boolean){const resolve=deleteResolver.current;deleteResolver.current=null;setDeletePrompt(null);resolve?.(value)}
  const nameResolver=useRef<((name:string|null)=>void)|null>(null)
  function askName(initial='',rename=false){return new Promise<string|null>(resolve=>{nameResolver.current=resolve;setNamePrompt({initial,rename})})}
  function resolveName(value:string|null){const resolve=nameResolver.current;nameResolver.current=null;setNamePrompt(null);resolve?.(value)}
  const [sid,setSid]=useState(()=>demo?'':sessionStorage.getItem(storageKey)||'')
  const sessionId=useRef(sid)
  const working=useRef(false)
  const [equipment,setEquipment]=useState<Equipment|null>(null)
  const [visual,setVisual]=useState<Visual>(emptyVisual)
  const [trace,setTrace]=useState<Trace|null>(null)
  const [pending,setPending]=useState<Pending[]>([])
  const [identifyPhotos,setIdentifyPhotos]=useState<Record<string,boolean>>({})
  const alive=useRef(true)
  const [removePhotoPrompt,setRemovePhotoPrompt]=useState<Photo|null>(null)
  const removePhotoResolver=useRef<((remove:boolean)=>void)|null>(null)
  function resolveRemovePhoto(value:boolean){const resolve=removePhotoResolver.current;removePhotoResolver.current=null;setRemovePhotoPrompt(null);resolve?.(value)}
  const [saveFeedback,setSaveFeedback]=useState(''),[uploading,setUploading]=useState('')
  useEffect(()=>{if(saveFeedback!=='Saved successfully')return;const timer=setTimeout(()=>setSaveFeedback(''),2500);return()=>clearTimeout(timer)},[saveFeedback])
  const pendingRef=useRef(pending);pendingRef.current=pending
  const [model,setModel]=useState(''),[match,setMatch]=useState(''),[symptom,setSymptom]=useState(''),[followup,setFollowup]=useState('')
  const [entryType,setEntryType]=useState<Draft['entry_type']>('answer')
  const [measurement,setMeasurement]=useState({name:'temperature',value:'',unit:'C',location:''})
  const [busy,setBusy]=useState(''),[error,setError]=useState(''),[notice,setNotice]=useState('')
  const [updateFeedback,setUpdateFeedback]=useState('')
  const [events,setEvents]=useState<string[]>([])
  const [source,setSource]=useState<Citation|null>(null),[sourceError,setSourceError]=useState(''),[sourceBusy,setSourceBusy]=useState(false)
  const sourceRequest=useRef(0),dialog=useRef<HTMLDialogElement>(null)
  const [replay,setReplay]=useState<Replay|null>(null)
  const activeSession=!!sid&&!!sessionName
  const saver=useSessionSave(demo?'':sid,{model,symptom,followup,entry_type:entryType,measurement},!!busy)
  function restoreDraft(id:string,draft:Draft){
    setModel(draft.model);setSymptom(draft.symptom);setFollowup(draft.followup);setEntryType(draft.entry_type);setMeasurement(draft.measurement);saver.hydrate(id,draft)
  }
  const confirmed=equipment?.confirmation_status==='CONFIRMED'
  const selectedCandidate=equipment?.ranked_candidates.find(c=>c.candidate_id===match)
  const confirmationBlocked=selectedCandidate?.confirmable===false
  const fixture=demo&&equipment?.confirmation_status==='FIXTURE'
  const result=trace?.result||emptyResult
  const failed=result.status==='failed'
  const usable=result.status==='suspected_cause'&&!!result.primary_cause
  const photos=visual.uploaded_images
  const savedPhotosRef=useRef(photos);savedPhotosRef.current=photos
  const findings=visual.aggregated_visual_findings.filter(f=>f.equipment_id==null||f.equipment_id===equipment?.confirmed_equipment_id)
  const newestRun=trace?.retrieved_evidence_history.at(-1)?.run_id
  const addEvent=(event:string)=>setEvents(old=>[...old,event])
  async function createSession(){
    const name=await askName()
    if(name===null)throw new DOMException('Session creation cancelled','AbortError')
    onSessionOperation?.('create')
    const eq=await request<Equipment & SessionMeta>('/sessions',json({session_name:name}))
    setSessionName(eq.session_name)
    sessionId.current=eq.session_id
    sessionStorage.setItem(storageKey,eq.session_id)
    setSid(eq.session_id);setEquipment(eq)
    return eq.session_id
  }
  async function ensureSession():Promise<string>{
    if(demo)throw new Error('Recorded replay does not create live sessions.')
    if(!sessionId.current||!sessionName)throw new Error('Start a new session or open one from My Sessions to begin.')
    return sessionId.current
  }

  async function refresh(id=sessionId.current){
    if(!id||demo)return
    const [meta,eq,v,t]=await Promise.all([request<SessionMeta>(`/sessions/${id}`),request<Equipment>(`/sessions/${id}/equipment`),request<Visual>(`/sessions/${id}/visual-findings`),request<Trace>(`/sessions/${id}/troubleshooting`)])
    setSessionName(meta.session_name);setEquipment(eq);setMatch(eq.confirmed_equipment_id||eq.ranked_candidates[0]?.candidate_id||'');setVisual(v);setTrace(t)
    return {eq,v,t}
  }
  async function work(label:string,operation:()=>Promise<void>){
    // Lock synchronously, before React renders disabled buttons, including reset.
    if(working.current)return
    working.current=true
    setBusy(label);setError('');setNotice('')
    try{if(!await saver.save())throw new Error('Save failed. Your draft is retained. Retry Save before continuing.');await operation()}catch(e){if(!(e instanceof DOMException&&e.name==='AbortError'))setError(e instanceof Error?e.message:'The request failed. Your workspace is retained.')}finally{working.current=false;setBusy('')}
  }
  useEffect(()=>{if(sid&&!demo)void work('Restoring session…',async()=>{try{await refresh(sid);restoreDraft(sid,await request<Draft>(`/sessions/${sid}/draft`))}catch(e){sessionStorage.removeItem(storageKey);sessionId.current='';setSid('');throw e}})},[]) // restored once; mutations refresh explicitly
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;nameResolver.current?.(null);deleteResolver.current?.(false);removePhotoResolver.current?.(false);for(const p of pendingRef.current)URL.revokeObjectURL(p.url)}},[])
  useEffect(()=>{if(source){dialog.current?.showModal()}else{dialog.current?.close()}},[!!source])
  function clearPending(){pending.forEach(p=>URL.revokeObjectURL(p.url));setPending([])}
  function resetDrafts(){
    setIdentifyPhotos({});setUpdateFeedback('');setSaveFeedback('');clearPending();setModel('');setMatch('');setSymptom('');setFollowup('')
    setEntryType('answer');setMeasurement({name:'temperature',value:'',unit:'C',location:''})
    sourceRequest.current++;setSource(null);setSourceError('');setSourceBusy(false)
  }
  function resetReplay(){resetDrafts();setReplay(null);setEquipment(null);setVisual(emptyVisual);setTrace(null);setSid('');setEvents([]);setError('')}
  function start(){void work('Creating session…',async()=>{
    await createSession()
    resetDrafts();saver.hydrate(sessionId.current,{model:'',symptom:'',followup:'',entry_type:'answer',measurement:{name:'temperature',value:'',unit:'C',location:''}});setTrace(null);setVisual(emptyVisual);setEvents(['Session started']);setPage('workspace')
  })}
  useEffect(()=>{if(initialPage==='history'&&!demo)void work('Loading sessions…',async()=>{await listSessions()})},[])
  async function listSessions(more=false){
    const rows=await request<SessionMeta[]>(`/sessions?limit=50&offset=${more?history.length:0}`)
    setHistory(old=>more?[...old,...rows]:rows);setHasMore(rows.length===50);setPage('history')
  }
  function reopen(id:string){void work('Opening saved session…',async()=>{
    onSessionOperation?.('reopen')
    const draft=await request<Draft>(`/sessions/${id}/draft`)
    const restored=await refresh(id)
    resetDrafts();setMatch(restored?.eq.confirmed_equipment_id||restored?.eq.ranked_candidates[0]?.candidate_id||'');sessionId.current=id;setSid(id);sessionStorage.setItem(storageKey,id)
    restoreDraft(id,draft);setEvents([]);setPage('workspace')
  })}
  function renameSession(row:SessionMeta){void work('Renaming session…',async()=>{
    const name=await askName(row.session_name,true);if(name===null)return
    await request(`/sessions/${row.id}`,{...json({session_name:name}),method:'PATCH'})
    if(row.id===sessionId.current)setSessionName(name)
    await listSessions()
  })}
  function deleteSession(row:SessionMeta){void work('Deleting session…',async()=>{
    const confirmed=await new Promise<boolean>(resolve=>{deleteResolver.current=resolve;setDeletePrompt(row)})
    if(!confirmed)return
    const result=await request<{deleted:boolean;file_cleanup_pending:boolean}>(`/sessions/${row.id}`,{method:'DELETE'})
    setHistory(old=>old.filter(item=>item.id!==row.id))
    if(row.id===sessionId.current){
      resetDrafts();sessionId.current='';setSid('');setSessionName('');setEquipment(null)
      setVisual(emptyVisual);setTrace(null);setEvents([]);sessionStorage.removeItem(storageKey);setPage('workspace')
    }
    setNotice(result.file_cleanup_pending?'Session deleted. Some photo files could not be removed; administrator cleanup is required.':'Session deleted.')
  })}
  async function addFiles(files:FileList|null){
    if(!activeSession||demo||busy||!files)return
    const id=sessionId.current,accepted=Array.from(files)
    for(const file of accepted){
      if(!['image/jpeg','image/png','image/webp'].includes(file.type)||file.size>10*1024*1024){setError('Choose JPEG, PNG or WEBP images up to 10 MB each.');continue}
      try{
        const bytes=await file.arrayBuffer()
        const fingerprint=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('')
        if(!alive.current||sessionId.current!==id)return
        if(pendingRef.current.some(p=>p.fingerprint===fingerprint)||savedPhotosRef.current.some(p=>p.content_sha256===fingerprint)){
          setNotice(`${file.name} is already attached to this session.`);continue
        }
        if(pendingRef.current.length+savedPhotosRef.current.length>=30){setError('This prototype accepts up to 30 photos per session.');continue}
        const photo={key:crypto.randomUUID(),fingerprint,file,url:URL.createObjectURL(file),view:'additional',note:'',ocr:true}
        pendingRef.current=[...pendingRef.current,photo];setPending(pendingRef.current)
      }catch{if(alive.current&&sessionId.current===id)setError('Could not read the selected photo. Please select it again.')}
    }
  }
  function selectSavedIdentification(photo:Photo,selected:boolean){void work('Saving identification selection…',async()=>{
    const updated=await request<Photo>(`/sessions/${sid}/images/${photo.id}/identification`,{...json({use_for_identification:selected}),method:'PATCH'})
    setIdentifyPhotos(old=>({...old,[photo.id]:selected}))
    setVisual(old=>({...old,uploaded_images:old.uploaded_images.map(p=>p.id===photo.id?updated:p)}))
  })}
  function inspectPhoto(photo:Photo){void work('Inspecting visible conditions…',async()=>{
    const id=await ensureSession()
    await request(`/sessions/${id}/images/${photo.id}/analyze`,{method:'POST'})
    await refresh(id)
  })}
  function removePhoto(photo:Photo){void work('Removing photo…',async()=>{
    const approved=await new Promise<boolean>(resolve=>{removePhotoResolver.current=resolve;setRemovePhotoPrompt(photo)})
    if(!approved)return
    const id=await ensureSession()
    const result=await request<{file_cleanup_pending:boolean}>(`/sessions/${id}/images/${photo.id}`,{method:'DELETE'})
    setVisual(old=>({...old,uploaded_images:old.uploaded_images.filter(p=>p.id!==photo.id)}))
    await refresh(id)
    setNotice(result.file_cleanup_pending?'Photo removed. Administrator file cleanup is required.':'Photo removed.')
  })}
  function photoStatus(photo:Photo){return ({pending:'Saved · Not analyzed',analyzing:'Analyzing…',completed:'Analysis complete',no_clear_abnormality:'Analysis complete',failed:'Analysis failed'} as Record<string,string>)[photo.analysis_status]||'Saved · Not analyzed'}
  async function upload(){
    const queue=[...pendingRef.current]
    if(!queue.length)return
    const id=await ensureSession()
    const failures:string[]=[]
    for(const photo of queue){
      if(!alive.current||sessionId.current!==id)return
      setUploading(photo.key)
      const form=new FormData();form.append('images',photo.file)
      form.append('identification_flags',JSON.stringify([photo.ocr||photo.view==='nameplate']));form.append('view_labels',JSON.stringify([photo.view]));form.append('user_notes',JSON.stringify([photo.note||null]))
      try{
        const created=await request<Photo[]>(`/sessions/${id}/images`,{method:'POST',body:form})
        if(!alive.current||sessionId.current!==id)return
        URL.revokeObjectURL(photo.url)
        pendingRef.current=pendingRef.current.filter(p=>p.key!==photo.key)
        setPending(pendingRef.current)
        savedPhotosRef.current=[...savedPhotosRef.current.filter(p=>!created.some(c=>c.id===p.id)),...created]
        if(photo.ocr||photo.view==='nameplate')setIdentifyPhotos(old=>({...old,...Object.fromEntries(created.map(p=>[p.id,true]))}))
        const savedImages=savedPhotosRef.current
        setVisual(old=>({...old,uploaded_images:savedImages}))
        addEvent('Photo saved; analysis has not been run')
      }catch(error){
        const message=error instanceof Error?error.message:'Photo upload failed.'
        failures.push(message)
        if(alive.current&&sessionId.current===id){
          pendingRef.current=pendingRef.current.map(p=>p.key===photo.key?{...p,saveError:message}:p)
          setPending(pendingRef.current)
        }
      }
      finally{if(alive.current)setUploading('')}
    }
    if(failures.length)throw new Error(`${failures[0]} Successfully uploaded photos are retained; retry saves only queued files.`)
  }
  async function manualSave(){
    if(working.current||demo||!activeSession)return
    const id=sessionId.current
    working.current=true;setBusy('Saving session…');setSaveFeedback('')
    try{
      if(!await saver.save())throw new Error('Draft save failed')
      if(!alive.current||sessionId.current!==id)return
      await upload()
      if(alive.current&&sessionId.current===id)setSaveFeedback('Saved successfully')
    }catch{
      if(alive.current&&sessionId.current===id)setSaveFeedback('Save failed')
    }finally{working.current=false;if(alive.current)setBusy('')}
  }
  async function identifyEquipment(){
    const selected=pendingRef.current.filter(p=>p.ocr||p.view==='nameplate')
    const saved=photos.filter(p=>identifyPhotos[p.id]??p.use_for_identification??p.view_label==='nameplate')
    if(selected.length+saved.length>30)throw new Error('Select at most thirty photos for equipment identification.')
    if(!model.trim()&&!selected.length&&!saved.length)throw new Error('Enter the model text or mark a nameplate photo for identification.')
    const id=await ensureSession()
    const form=new FormData();form.append('entered_equipment_text',model);form.append('use_visual','true')
    form.append('saved_image_ids',JSON.stringify(saved.map(p=>p.id)))
    selected.forEach(p=>form.append('images',p.file));form.append('image_roles',JSON.stringify(selected.map(p=>p.view==='nameplate'?'nameplate':'equipment')))
    const eq=await request<Equipment>(`/sessions/${id}/equipment/identify`,{method:'POST',body:form})
    setEquipment(eq);setMatch(eq.ranked_candidates[0]?.candidate_id||'');setTrace(null);addEvent('Equipment identification updated; confirmation required')
    await refresh(id)
  }
  function identify(){void work('Reading nameplate and matching equipment…',identifyEquipment)}
  function confirm(){void work('Confirming equipment and saving photos…',async()=>{
    const id=await ensureSession()
    const eq=await request<Equipment>(`/sessions/${id}/equipment/confirm`,json({equipment_id:match,identification_revision:equipment?.identification_revision}))
    if(eq.confirmation_status!=='CONFIRMED'||!eq.confirmed_equipment_id||!eq.confirmed_model)throw new Error('Equipment confirmation was not completed. Review the candidate and try again.')
    setEquipment(eq);setMatch(eq.confirmed_equipment_id);setTrace(null);addEvent(`Equipment confirmed: ${eq.confirmed_model}`)
    // The committed confirmation response is authoritative. Upload updates photo
    // state independently; a redundant equipment read could restore stale state.
    await upload()
  })}
  function analyze(){void work('Inspecting visible conditions…',async()=>{
    const id=await ensureSession()
    if(!confirmed&&(model.trim()||pendingRef.current.some(p=>p.ocr||p.view==='nameplate')||photos.some(p=>identifyPhotos[p.id]??p.use_for_identification??p.view_label==='nameplate')))await identifyEquipment()
    await upload()
    if(!confirmed){await refresh(id);setNotice('Photos saved. Review and confirm the equipment match, then inspect visible conditions.');return}
    // analyze-all intentionally skips failed images; retry those explicitly.
    const current=await request<Photo[]>(`/sessions/${id}/images`)
    for(const p of current.filter(p=>(p.equipment_id===null||p.equipment_id===equipment?.confirmed_equipment_id)&&['pending','failed'].includes(p.analysis_status))){
      await request(`/sessions/${id}/images/${p.id}/analyze`,{method:'POST'})
    }
    const updated=await refresh();addEvent('Visible inspection results updated')
    if(updated?.v.uploaded_images.some(p=>p.equipment_id===updated.eq.confirmed_equipment_id&&p.analysis_status==='failed'))setError('Some photos could not be analyzed. They remain saved. Retry visible inspection when the service is available.')
  })}
  function run(){void work('Checking ABB documentation…',async()=>{
    if(!confirmed)throw new Error('Confirm the equipment model before running troubleshooting.')
    const id=await ensureSession()
    if(symptom.trim()){setTrace(await request<Trace>(`/sessions/${id}/troubleshooting/symptoms`,json({symptom})));addEvent(`Symptom added: ${symptom}`)}
    const t=await request<Trace>(`/sessions/${id}/troubleshooting/run`,{method:'POST'})
    setTrace(t);addEvent(t.result.status==='failed'?'Troubleshooting service unavailable':'Troubleshooting result updated')
  })}
  function guidance(r:Result){return JSON.stringify([r.status,r.primary_cause,r.alternative_causes,r.recommended_actions,r.confidence,r.next_question,r.sources.map(c=>c.chunk_id).sort()])}
  function follow(){void work('Checking ABB documentation with your update…',async()=>{
    const id=await ensureSession()
    const input=entryType==='measurement'?{measurements:[measurement]}:entryType==='check'?{checks_completed:[followup]}:{answer:followup}
    const previous=guidance(result)
    setUpdateFeedback('')
    try{
      const t=await request<Trace>(`/sessions/${id}/troubleshooting/follow-up`,json({...input,expected_revision:trace?.revision}))
      setTrace(t)
      const recorded=entryType==='measurement'?`${measurement.name} ${measurement.value} ${measurement.unit}`:followup
      addEvent(`Update saved: ${recorded}`)
      setUpdateFeedback(t.result.status==='failed'?'Update saved. Troubleshooting is unavailable; your entry is retained for retry.':previous===guidance(t.result)?'Update saved. No new troubleshooting guidance was found from this information.':'Update saved. Troubleshooting guidance refreshed; review the result and next checks above.')
      if(t.result.status!=='failed'){setFollowup('');setMeasurement({...measurement,value:''})}
    }catch(e){
      // The input transaction may have committed before retrieval failed. Refresh
      // persisted state without clearing the draft or retrying a provider call.
      try{await refresh(id)}catch{/* Keep the last known case and retry draft. */}
      setUpdateFeedback('The documentation check did not complete. Your entry is retained for retry; check saved activity below.')
      throw e
    }
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
    const raw=all[key];const saved={...raw,equipment:normalizeEquipment(raw.equipment) as Equipment,trace:normalizeTrace(raw.trace) as Trace,visual:normalizeVisual(raw.visual) as Visual};resetDrafts();setReplay(saved);setEquipment(saved.equipment);setTrace(saved.trace);setVisual(saved.visual);setSid(saved.equipment.session_id)
    setEvents(['Prepared record loaded — replay, not a fresh analysis']);setSymptom(saved.trace.reported_symptoms.join('; '))
  })}
  const steps=[['01','Equipment & photos',confirmed],['02','What’s happening',!!symptom.trim()],['03','Troubleshooting',usable],['04','Follow-up',!!trace?.follow_up_answers.length]] as const
  return <>
    <header className="topbar"><a className="brand" href="/" aria-label="FieldTrace home"><span className="brand-mark">F<span>↗</span></span><span>FieldTrace<small>MAINTENANCE INTELLIGENCE</small></span></a><div className="top-meta"><span className="prototype-label">ABB ACCELERATOR · PROTOTYPE</span><span className="live-dot"/>{demo?'RECORDED REPLAY':'TECHNICIAN WORKSPACE'}{!demo&&<nav className="account-nav" aria-label="Account"><button disabled={!!busy} onClick={()=>void work('Loading sessions…',async()=>{await listSessions()})}>My Sessions</button><button disabled={!!busy} onClick={()=>setPage('workspace')}>Workspace</button>{account}</nav>}{demo&&<a href="/">Log in for live use</a>}</div></header>
    {demo&&<aside className="replay-banner"><strong>DEMO REPLAY · Not a fresh analysis</strong><span>Prepared records only. Live upload, OCR and model calls are disabled.</span><div>{['acs880','motor','visual'].map((k,i)=><button key={k} disabled={!!busy} onClick={()=>void loadReplay(k)}>{['ACS880 fault 5091','Motor uncertainty fixture','Recorded visible finding'][i]}</button>)}<button disabled={!!busy} onClick={resetReplay}>Reset demo</button></div>{replay&&<p>{replay.disclosure}</p>}</aside>}
    {removePhotoPrompt&&<RemovePhotoDialog name={removePhotoPrompt.original_filename} onDone={resolveRemovePhoto}/>}
    {deletePrompt&&<DeleteSessionDialog name={deletePrompt.session_name} onDone={resolveDelete}/>}
    {namePrompt&&<NameDialog initial={namePrompt.initial} rename={namePrompt.rename} onDone={resolveName}/>}
    <main>
      {page==='history'&&<section className="panel session-history"><h1>My Sessions</h1>{!history.length?<><p>No troubleshooting sessions yet.</p><button className="primary" disabled={!!busy} onClick={start}>Start a troubleshooting session</button></>:history.map(row=><article className="session-card" key={row.id}><h2><button className="session-title" disabled={!!busy} onClick={()=>reopen(row.id)}>{row.session_name}</button></h2><p>{row.confirmed_model||'Equipment unconfirmed'} · {row.symptom_summary||'No reported symptom'}</p><p>{row.result_status.replaceAll('_',' ')}{row.confidence?` · ${row.confidence}`:''}</p><small>Created {new Date(row.created_at).toLocaleString()} · Updated {new Date(row.updated_at).toLocaleString()}</small><div><button className="primary" disabled={!!busy} onClick={()=>reopen(row.id)}>Continue troubleshooting</button><button disabled={!!busy} onClick={()=>renameSession(row)}>Rename</button><button className="text-button danger-text" disabled={!!busy} onClick={()=>deleteSession(row)}>Delete</button></div></article>)}{hasMore&&<button disabled={!!busy} onClick={()=>void work('Loading sessions…',async()=>{await listSessions(true)})}>Load more sessions</button>}</section>}
      <div hidden={page!=='workspace'}>
      <section className="page-heading"><div><p className="eyebrow">{!demo&&activeSession?'CURRENT SESSION':'TECHNICIAN WORKSPACE'}</p><h1 className="current-session-name">{!demo&&activeSession?sessionName:<>From observation<br className="mobile-break"/> to evidence.</>}</h1><p>Equipment, photo observations and symptoms connected to cited ABB evidence.</p></div><div className="heading-actions">{!demo&&activeSession&&<div className="save-controls"><button disabled={!!busy} onClick={()=>void manualSave()}>Save</button>{saveFeedback&&<small role="status">{saveFeedback}</small>}{saveFeedback==='Save failed'&&<small>Drafts and unsaved photos are retained. Retry Save.</small>}{saver.status==='Save failed'&&saveFeedback!=='Save failed'&&<small role="status">Auto-save failed. Your draft is retained; use Save to retry.</small>}</div>}<button className="primary new-session" disabled={!!busy||demo} onClick={start}><span>＋</span> Start new troubleshooting session</button></div></section>
      <nav className="progress" aria-label="Troubleshooting steps">{steps.map(([n,title,done])=><div className={done?'done':''} key={n}><span>{done?'✓':n}</span>{title}</div>)}<span className="session-status">{sid?`Session ${sessionName||sid.slice(0,8)} · ${fixture?'Temporary reasoning fixture':confirmed?'Equipment confirmed':'Awaiting confirmation'}`:'No active session'}</span></nav>
      </div>
      {error&&<div className="alert error" role="alert"><strong>Request not completed</strong><p>{error}</p>{sid&&!demo&&<button disabled={!!busy} onClick={()=>void work('Refreshing session…',async()=>{await refresh()})}>Refresh session status</button>}</div>}
      {notice&&<p role="status">{notice}</p>}
      {busy&&busy!=='Saving session…'&&<div className="working" role="status"><span className="spinner"/><div>{busy}{busy.startsWith('Checking ABB')&&<small>Search, evidence review and claim verification can take a minute. Your session stays here; no photo processing is repeated.</small>}</div></div>}
      {!demo&&!activeSession&&page==='workspace'&&<section className="panel locked-session" aria-label="No active troubleshooting session"><h2>No active troubleshooting session</h2><p>Start a new session or open one from My Sessions to begin.</p></section>}
      <fieldset className="workspace-gate" disabled={!demo&&!activeSession} hidden={page!=='workspace'}>
      <div className="workspace">
        <div className="intake">
          <section className="panel"><SectionTitle number="01" title="Equipment & photos" detail="Add a clear nameplate photo and areas showing visible damage."/>
            <fieldset disabled={!!busy||demo}>
              <label className="upload-box"><span className="upload-symbol">＋</span><strong>Add equipment photos</strong><span>JPEG, PNG or WEBP · up to 10 MB each</span><input aria-label="Add equipment photos" type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={e=>{addFiles(e.target.files);e.target.value=''}}/></label>
              {pending.length>0&&<p className="hint">{confirmed?'Ready to upload.':'Photos are queued locally. Model text is optional. Selected photos provide readable text and provisional visual family evidence during identification.'}</p>}
              <div className="photo-list">{pending.map(p=><article className="pending-photo" key={p.key}><img src={p.url} alt={p.file.name}/><div><strong title={p.file.name}>{p.file.name}</strong><small className="file-save-state">{uploading===p.key?'Uploading…':'Queued'}</small>{p.saveError&&<small className="warning-note">{p.saveError}</small>}<label>View<select aria-label={`View for ${p.file.name}`} value={p.view} onChange={e=>setPending(old=>old.map(x=>x.key===p.key?{...x,view:e.target.value}:x))}>{labels.map(l=><option key={l} value={l}>{l.replace('_','-')}</option>)}</select></label><label>Photo note<input value={p.note} maxLength={1200} onChange={e=>setPending(old=>old.map(x=>x.key===p.key?{...x,note:e.target.value}:x))} placeholder="Optional observation"/></label><label className="checkbox"><input type="checkbox" checked={p.ocr||p.view==='nameplate'} onChange={e=>setPending(old=>old.map(x=>x.key===p.key?{...x,ocr:e.target.checked}:x))}/>Use for identification</label><button className="text-button" onClick={()=>{URL.revokeObjectURL(p.url);setPending(old=>old.filter(x=>x.key!==p.key))}}>Remove queued photo</button></div></article>)}</div>
              <label>Model text, if known<input value={model} onChange={e=>setModel(e.target.value)} placeholder="e.g. ABB ACS880-01" maxLength={1000}/></label>
              {!confirmed&&!equipment?.ranked_candidates.length&&!equipment?.identification?.specificity&&<button className="text-button" onClick={identify}>Detect equipment / read nameplate</button>}
              <button className="primary full-width" disabled={!pending.length&&!photos.some(p=>['pending','failed'].includes(p.analysis_status))} onClick={analyze}>Save photos & inspect visible conditions</button>
            </fieldset>
            {equipment&&<div className="equipment-result"><div className="row"><p className="eyebrow">{fixture?'REASONING FIXTURE':confirmed?'CONFIRMED EQUIPMENT':'DETECTED EQUIPMENT'}</p>{equipment.confidence&&<Badge value={equipment.confidence}/>}</div><h3>{equipment.identification?.label||(confirmed||fixture?equipment.confirmed_model:equipment.ranked_candidates[0]?.candidate_model||'Unable to identify confidently. Upload a clear nameplate or front-panel photo.')}</h3>{equipment.identification&&<div className="identification-explanation"><small>{equipment.identification.specificity.replaceAll('_',' ')} · Confidence: {equipment.identification.confidence}</small><h4>Why</h4><p>{equipment.identification.why}</p><h4>To confirm</h4><p>{equipment.identification.to_confirm}</p>{equipment.identification.provider_error&&<p className="warning-note">{equipment.identification.provider_error}</p>}</div>}<p>{confirmed||fixture?equipment.confirmed_equipment_family:'Review the match before continuing.'}</p>{equipment.mismatch_warnings.map((w,i)=><p className="warning-note" key={i}>{w}</p>)}{!confirmed&&equipment.ranked_candidates.length>0&&<fieldset disabled={!!busy||demo}><label>Choose match<select value={match} onChange={e=>setMatch(e.target.value)}>{equipment.ranked_candidates.map(c=><option key={c.candidate_id} value={c.candidate_id}>{c.confirmable===false?`${c.equipment_family} family — subtype unconfirmed`:c.candidate_model} · {c.match_level}</option>)}</select></label><button className="primary full-width" disabled={!match||confirmationBlocked} onClick={confirm}>Confirm equipment</button>{confirmationBlocked&&<p className="hint" role="status">Family-level evidence cannot confirm this model. Enter the exact model text or upload a readable model label/nameplate, then run Detect equipment again.</p>}</fieldset>}{!demo&&<button className="text-button" disabled={!!busy} onClick={identify}>{confirmed||equipment.ranked_candidates.length||(equipment.identification&&equipment.identification.specificity!=='insufficient')?'Correct equipment':'Retry equipment identification'}</button>}{equipment.raw_ocr_text&&<details><summary>Read nameplate text</summary><pre>{equipment.raw_ocr_text}</pre></details>}</div>}

          <h3>Visible findings</h3><p className="hint">Photo observations are visual evidence only, not a diagnosis.</p>
            {photos.length>0&&<div className="saved-photos">{photos.map(p=><figure key={p.id}><>{demo?<img src={replay?.image_urls?.[p.id]} alt={p.original_filename}/>:<PrivatePhoto path={`/sessions/${sid}/images/${p.id}/file`} alt={p.original_filename}/>}</><figcaption>{p.view_label.replace('_','-')}<small>{photoStatus(p)}</small></figcaption>{p.user_note&&<p className="hint">Technician note: {p.user_note}</p>}{!demo&&<label className="checkbox"><input type="checkbox" disabled={!!busy} checked={identifyPhotos[p.id]??p.use_for_identification??p.view_label==='nameplate'} onChange={e=>selectSavedIdentification(p,e.target.checked)}/>Use saved photo for identification</label>}{!demo&&<div className="photo-actions"><button disabled={!!busy||!confirmed||p.analysis_status==='analyzing'||['completed','no_clear_abnormality'].includes(p.analysis_status)||(p.equipment_id!==null&&p.equipment_id!==equipment?.confirmed_equipment_id)} onClick={()=>inspectPhoto(p)}>Inspect / Analyze</button><button disabled={!!busy} onClick={()=>removePhoto(p)}>Remove</button></div>}</figure>)}</div>}
            {findings.map(f=><article className="finding" key={f.id}><span className="finding-marker"/><div><strong>{f.issue_type.replaceAll('_',' ')}</strong><p>{f.description}</p><small>Visual confidence: {f.visual_confidence.toUpperCase()} · {(f.supporting_image_ids||[f.image_id]).map(id=>photos.find(p=>p.id===id)?.view_label.replace('_','-')||'recorded image').join(', ')}</small></div></article>)}
            {!findings.length&&photos.length>0&&photos.every(p=>p.analysis_status==='no_clear_abnormality')?<p className="neutral-message">No obvious visible abnormality detected in these images.</p>:!findings.length&&<p className="empty-copy">{photos.some(p=>p.analysis_status==='failed')?'Image analysis is unavailable. No findings have been substituted.':'Uploaded photos will appear here with their visible observations.'}</p>}
            {photos.some(p=>p.analysis_status==='failed')&&<p className="warning-note">Some images failed analysis. Retry when the provider is available.</p>}
            {visual.uploaded_images.length>photos.length&&<p className="hint">Earlier photos belong to a different confirmation state and are not included. Upload fresh views for this equipment.</p>}
            {confirmed&&pending.length>0&&<button className="text-button full-width" disabled={!!busy||demo} onClick={()=>void work('Saving photos…',upload)}>Save photos without analysis</button>}
            {replay?.attribution&&<p className="hint">{replay.attribution}</p>}
          </section>
        </div>
        <div className="results-column">
          <section className="panel problem"><SectionTitle number="02" title="What’s happening" detail="Describe the issue or enter an exact fault code, such as 5091."/><fieldset disabled={!!busy||demo}><label>What problem are you seeing?<textarea value={symptom} maxLength={1200} onChange={e=>setSymptom(e.target.value)} placeholder="Drive shows fault 5091. Motor is overheating. There is an unusual noise." rows={3}/></label><div className="run-row"><small>{demo?'Recorded example — live processing is disabled.':confirmed?'Confirmed equipment will scope the documentation search.':'Confirm the equipment model before running troubleshooting.'}</small><button className="primary" disabled={!confirmed||(!symptom.trim()&&!trace?.reported_symptoms.length)} onClick={run}>Run troubleshooting <span>→</span></button></div></fieldset></section>
          <section className="panel result-panel" aria-label="Troubleshooting result"><div className="result-title"><p className="eyebrow">03 · DOCUMENTED TROUBLESHOOTING</p>{!failed&&!['not_run','stale'].includes(result.status)&&<Badge value={result.confidence}/>}</div>
            {!failed&&!['not_run','stale'].includes(result.status)&&<p className="confidence-guide">HIGH: stronger evidence · MEDIUM: supported direction, more checks needed · LOW: more information needed. These are evidence levels, not probabilities.</p>}
            {failed?<div className="result-empty"><h2>Troubleshooting service unavailable</h2><p>Your session inputs are saved. No new diagnosis was generated. Try again when the service is available.</p><button disabled={!!busy||demo} onClick={()=>void work('Checking ABB documentation…',async()=>{const id=await ensureSession();setTrace(await request<Trace>(`/sessions/${id}/troubleshooting/run`,{method:'POST'}))})}>Retry troubleshooting</button></div>:
            usable?<><p className="result-label">What this means · suspected cause</p><h2 className="cause-title">{result.primary_cause!.label}</h2><p className="result-disclaimer">{result.message}</p><div className="rationale"><h3>Why this matches</h3><p>{result.primary_cause!.rationale}</p>{cites(result.primary_cause!.citation_chunk_ids)}</div>
            {result.alternative_causes.length>0&&<div className="result-section"><h3>Other possible causes</h3>{result.alternative_causes.map((c,i)=><div key={i}><strong>{c.label}</strong><p>{c.rationale}</p>{cites(c.citation_chunk_ids)}</div>)}</div>}
            <div className="result-section"><h3>What to check next</h3>{result.recommended_actions.length?<ol className="checks">{result.recommended_actions.map((a,i)=><li key={i}><p>{a.action}</p>{cites(a.citation_chunk_ids)}</li>)}</ol>:<p className="empty-copy">No supported checks returned for this run.</p>}</div>
            {result.technical_claims.length>0&&<details className="claims"><summary>Technical statements & sources</summary>{result.technical_claims.map(c=><div key={c.claim_id}><p>{c.text}</p>{cites(c.citation_chunk_ids)}</div>)}</details>}</>:
            ['not_run','stale'].includes(result.status)?<div className="result-empty"><div className="document-symbol">≡</div><h2>{result.status==='stale'?'Session changed. Run troubleshooting again.':'A clearer next step starts with evidence.'}</h2><p>Confirmed equipment, visible observations and your symptom bring the relevant ABB documentation into this workspace.</p><div className="empty-tags"><span>Exact manual pages</span><span>Cited technical statements</span><span>Useful follow-up questions</span></div></div>:
            <div className="result-empty low-evidence"><span className="result-label">MORE EVIDENCE NEEDED</span><h2>We need more information before narrowing this down.</h2><p>{result.message}</p></div>}
            {result.conflicts.filter(c=>['CONFLICTING','DIFFERENT_APPLICABILITY'].includes(c.relationship)).map((c,i)=><aside className="conflict" key={i}><h3>Some source guidance differs.</h3><p>{c.relationship==='DIFFERENT_APPLICABILITY'?'These sources have different applicability. Confirm the model, revision and operating conditions.':'The backend flagged conflicting guidance. Review these sources before proceeding.'}</p>{cites(c.citation_chunk_ids)}</aside>)}
            {result.next_question&&!failed&&!['not_run','stale'].includes(result.status)&&<aside className="next-question"><p className="eyebrow">NEXT QUESTION</p><h3>{result.next_question}</h3>{cites(result.question_sources)}</aside>}
            {sid&&trace&&(result.status!=='not_run'||!!updateFeedback||trace.retrieved_evidence_history.length>0)&&<div className="follow-up"><SectionTitle number="04" title="Add more information" detail="Continue this session with an answer, measurement or completed check."/>{updateFeedback&&<p role="status">{updateFeedback}</p>}<fieldset disabled={!!busy||demo||!confirmed}><label>Entry type<select value={entryType} onChange={e=>setEntryType(e.target.value as Draft['entry_type'])}><option value="answer">Answer / observation / fault code</option><option value="check">Completed check</option><option value="measurement">Measurement</option></select></label>{entryType==='measurement'?<div className="measurement-grid">{(['name','value','unit','location'] as const).map(k=><label key={k}>{k}<input value={measurement[k]} onChange={e=>setMeasurement({...measurement,[k]:e.target.value})} maxLength={80}/></label>)}</div>:<label>Update for this session<textarea value={followup} maxLength={1200} onChange={e=>setFollowup(e.target.value)} placeholder="The cooling fan is running. Temperature is 92 C. I cleaned the vents and it is still overheating." rows={2}/></label>}<button className="secondary" disabled={entryType==='measurement'?(!measurement.name.trim()||!measurement.value.trim()):!followup.trim()} onClick={follow}>Submit update & check documentation →</button></fieldset></div>}
          </section>
          <section className="panel source-list"><div className="row"><h2>Sources</h2><span className="count">{result.sources.length}</span></div>{result.sources.length?result.sources.map(c=><button key={c.chunk_id} className="source-row" onClick={()=>void openSource(c)}><span className="page-icon">PDF</span><span><strong>{c.document_title}</strong><small>Page {c.page_number}{c.section_title?` · ${c.section_title}`:''}</small></span><span>↗</span></button>):<p className="empty-copy">Cited ABB manual pages will appear after a supported result.</p>}</section>
          <section className="panel history"><h2>Session activity</h2><ol>{events.map((e,i)=><li key={`local-${i}`}>{e}</li>)}{trace?.reported_symptoms.map((v,i)=><li key={`s${i}`}>Reported symptom: {v}</li>)}{trace?.follow_up_answers.map((v,i)=><li key={`f${i}`}>Follow-up saved: {v}</li>)}{trace?.checks_completed.map((v,i)=><li key={`c${i}`}>Completed check: {v}</li>)}{trace?.measurements.map((m,i)=><li key={`m${i}`}>Measurement: {m.name} {m.value} {m.unit} · {m.location}</li>)}{trace?.retrieved_evidence_history.map(r=><li key={r.run_id}>Documentation check · {r.status.replaceAll('_',' ')}<small>{new Date(r.created_at).toLocaleString()}</small></li>)}</ol>{!events.length&&!trace?.retrieved_evidence_history.length&&<p className="empty-copy">Equipment confirmation, checks and follow-ups are recorded here.</p>}{sid&&!demo&&<button className="text-button" disabled={!!busy} onClick={()=>void work('Refreshing session…',async()=>{await refresh()})}>Refresh saved session</button>}</section>
        </div>
      </div>
      </fieldset>
      <footer><span>FieldTrace <b>/</b> ABB Accelerator 2026</span><span>Prototype · Source-backed support for technician review</span></footer>
    </main>
    <dialog ref={dialog} onCancel={()=>{sourceRequest.current++;setSource(null)}} onClick={e=>{if(e.target===dialog.current){dialog.current.close();sourceRequest.current++;setSource(null)}}}><div className="source-dialog">{source&&<><div className="row"><p className="eyebrow">SOURCE EVIDENCE</p><button aria-label="Close source viewer" onClick={()=>{dialog.current?.close();sourceRequest.current++;setSource(null)}}>✕</button></div><h2>{source.document_title}</h2><p>Page {source.page_number}{source.section_title?` · ${source.section_title}`:''}</p><p className="hint">{source.document_number}{source.revision?` · Revision ${source.revision}`:''}</p>{sourceBusy?<p role="status">Loading exact cited excerpt…</p>:sourceError?<div role="alert"><p>{sourceError}</p><button onClick={()=>void openSource(source)}>Retry source</button></div>:<><h3>Exact cited chunk</h3><pre className="excerpt">{source.chunk_text}</pre><p className="hint">Technical evidence comes from cited ABB documentation. This is the exact stored excerpt; no highlights have been added.</p></>}{safeLink(source.citation_url||source.source_url)&&<a className="primary link-button" href={safeLink(source.citation_url||source.source_url)} target="_blank" rel="noopener noreferrer">Open manual page ↗</a>}{safeLink(source.source_url)&&<p className="source-url"><a href={safeLink(source.source_url)} target="_blank" rel="noopener noreferrer">{source.source_url}</a></p>}</>}</div></dialog>
  </>
}
