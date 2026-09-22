// Vite replaces this public setting at build time. Never put secrets in VITE_*.
export function apiUrl(path:string):string {
  const base=(import.meta.env.VITE_API_BASE_URL || '').trim().replace(/\/+$/,'') || '/api'
  return base+'/'+path.replace(/^\/+/, '')
}
export class ApiError extends Error { constructor(message:string,public status=0){super(message)} }
export async function request<T>(path:string,options:RequestInit={}):Promise<T>{
  const controller = new AbortController()
  // The backend has a bounded multi-call workflow. Permit it to finish; timeout
  // means the caller must refresh state because the server may still be running.
  const timer = setTimeout(()=>controller.abort(),15*60*1000)
  try {
    const response=await fetch(apiUrl(path),{...options,signal:controller.signal})
    if(!response.ok){
      const body=await response.json().catch(()=>null)
      const detail=typeof body?.detail==='string'?body.detail:null
      throw new ApiError(response.status===429?'Service rate limit reached. Please wait and retry.':
        response.status>=500?'The service is temporarily unavailable. Refresh session status before retrying.':
        detail||`Request could not be completed (${response.status}).`,response.status)
    }
    return await response.json() as T
  }catch(error){
    if(error instanceof ApiError)throw error
    throw new ApiError(error instanceof DOMException&&error.name==='AbortError'?
      'The request timed out. It may still be running; refresh session status before retrying.':
      'Cannot reach the backend. Your current workspace is retained. Check the connection and refresh status.')
  }finally{clearTimeout(timer)}
}
export const json = (body:unknown):RequestInit=>({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
export function safeLink(url:string|null|undefined){try{const u=new URL(url||'');return ['https:','http:'].includes(u.protocol)?u.href:undefined}catch{return undefined}}
