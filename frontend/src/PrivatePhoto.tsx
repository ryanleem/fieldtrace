import {useEffect,useState} from 'react'
import {apiUrl} from './api'
import {authHeaders} from './auth'

export default function PrivatePhoto({path,alt}:{path:string;alt:string}){
  const [src,setSrc]=useState(''),[error,setError]=useState(false)
  useEffect(()=>{
    let active=true,url='';const controller=new AbortController()
    setSrc('');setError(false)
    void (async()=>{
      try{
        const r=await fetch(apiUrl(path),{headers:await authHeaders(),signal:controller.signal,cache:'no-store'})
        if(!r.ok)throw new Error('Image unavailable')
        const blob=await r.blob()
        if(active){url=URL.createObjectURL(blob);setSrc(url)}
      }catch{if(active)setError(true)}
    })()
    return()=>{active=false;controller.abort();if(url)URL.revokeObjectURL(url)}
  },[path])
  return src?<img src={src} alt={alt}/>:<span>{error?'Saved photo unavailable. Refresh after signing in again.':'Loading saved photo…'}</span>
}
