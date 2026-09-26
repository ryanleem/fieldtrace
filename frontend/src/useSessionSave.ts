import {useEffect,useRef,useState} from 'react'
import {json,request} from './api'
export type Draft={model:string;symptom:string;followup:string;entry_type:'answer'|'check'|'measurement';measurement:{name:string;value:string;unit:string;location:string}}
export default function useSessionSave(id:string,draft:Draft,paused:boolean){
 const [status,setStatus]=useState('Saved'),[saving,setSaving]=useState(false)
 const current=useRef({id,draft});current.current={id,draft}
 const baseline=useRef<{id:string;value:string}|null>(null),flight=useRef<Promise<boolean>|null>(null),mounted=useRef(true)
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false}},[])
 function hydrate(session:string,value:Draft){baseline.current={id:session,value:JSON.stringify(value)};setStatus('Saved')}
 async function save():Promise<boolean>{
  if(flight.current){const ok=await flight.current;return ok?save():false}
  const active=current.current,base=baseline.current
  if(!mounted.current||!active.id||base?.id!==active.id)return true
  const value=JSON.stringify(active.draft)
  if(value===base.value)return true
  setSaving(true);setStatus('Saving…')
  const operation=(async()=>{
   try{
    await request(`/sessions/${active.id}/draft`,{...json(active.draft),method:'PUT'})
    if(mounted.current&&current.current.id===active.id&&baseline.current===base){base.value=value;setStatus(JSON.stringify(current.current.draft)===value?'Saved':'Unsaved changes')}
    return true
   }catch{if(mounted.current&&current.current.id===active.id)setStatus('Save failed');return false}
   finally{flight.current=null;if(mounted.current)setSaving(false)}
  })()
  flight.current=operation
  const ok=await operation
  return ok&&mounted.current&&current.current.id===active.id?save():ok
 }
 const value=JSON.stringify(draft)
 useEffect(()=>{
  if(!id||baseline.current?.id!==id||baseline.current.value===value)return
  setStatus('Unsaved changes')
  if(paused)return
  const timer=setTimeout(()=>{void save()},850)
  return()=>clearTimeout(timer)
 },[id,value,paused])
 return {hydrate,save,status,saving}
}
