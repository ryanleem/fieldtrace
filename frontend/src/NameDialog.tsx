import {useEffect,useRef,useState} from 'react'

export default function NameDialog({initial,rename,onDone}:{initial:string;rename:boolean;onDone:(name:string|null)=>void}){
  const [name,setName]=useState(initial),ref=useRef<HTMLDialogElement>(null),done=useRef(false)
  function finish(value:string|null){if(!done.current){done.current=true;onDone(value)}}
  useEffect(()=>{ref.current?.showModal()},[])
  return <dialog ref={ref} aria-label={rename?'Rename session':'Name your troubleshooting session'} onCancel={e=>{e.preventDefault();finish(null)}}><form className="source-dialog" onSubmit={e=>{e.preventDefault();if(name.trim())finish(name.trim())}}>
    <h2>{rename?'Rename session':'Start a troubleshooting session'}</h2>
    <label>Session name<input autoFocus required maxLength={100} value={name} onChange={e=>setName(e.target.value)} placeholder="e.g. ACS880 Fault 5091"/></label>
    <div className="dialog-actions"><button type="button" onClick={()=>finish(null)}>Cancel</button><button className="primary" disabled={!name.trim()}>{rename?'Save name':'Start session'}</button></div>
  </form></dialog>
}
