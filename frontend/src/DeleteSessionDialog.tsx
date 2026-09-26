import {useEffect,useRef} from 'react'

export default function DeleteSessionDialog({name,onDone}:{name:string;onDone:(confirmed:boolean)=>void}){
 const ref=useRef<HTMLDialogElement>(null),done=useRef(false)
 function finish(value:boolean){if(!done.current){done.current=true;onDone(value)}}
 useEffect(()=>{ref.current?.showModal()},[])
 return <dialog ref={ref} aria-label="Delete troubleshooting session?" onCancel={e=>{e.preventDefault();finish(false)}}><div className="source-dialog">
  <h2>Delete troubleshooting session?</h2>
  <p>“{name}” and its saved troubleshooting history, photos, findings, checks and follow-ups will be permanently removed.</p>
  <div className="dialog-actions"><button autoFocus onClick={()=>finish(false)}>Cancel</button><button className="danger" onClick={()=>finish(true)}>Delete session</button></div>
 </div></dialog>
}
