import {useEffect,useRef} from 'react'
export default function RemovePhotoDialog({name,onDone}:{name:string;onDone:(remove:boolean)=>void}){
 const ref=useRef<HTMLDialogElement>(null),done=useRef(false)
 function finish(value:boolean){if(!done.current){done.current=true;onDone(value)}}
 useEffect(()=>{ref.current?.showModal()},[])
 return <dialog ref={ref} aria-label="Remove this photo?" onCancel={e=>{e.preventDefault();finish(false)}}><div className="source-dialog"><h2>Remove this photo?</h2><p>{name}: Its saved visual findings will also be removed from this session.</p><div className="dialog-actions"><button autoFocus onClick={()=>finish(false)}>Cancel</button><button className="danger" onClick={()=>finish(true)}>Remove photo</button></div></div></dialog>
}
