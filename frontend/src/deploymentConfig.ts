// Return variable names and guidance only; never echo configuration values.
export type FrontendEnv=Record<string,string|boolean|undefined>
export function localHost(host:string){return ['localhost','127.0.0.1','[::1]'].includes(host)}
function validUrl(value:string,hosted:boolean){
 try{const u=new URL(value);return !u.username&&!u.password&&!u.search&&!u.hash&&
  (u.protocol==='https:'||(!hosted&&u.protocol==='http:'&&localHost(u.hostname)))&&
  (!hosted||!localHost(u.hostname))}catch{return false}
}
export function liveConfigErrors(env:FrontendEnv,hosted:boolean):string[]{
 const text=(name:string)=>String(env[name]??'').trim()
 const errors:string[]=[]
 const demo=String(env.VITE_DEMO_MODE??'')
 if(demo&&!['true','false'].includes(demo))errors.push('VITE_DEMO_MODE must be true or false (default false).')
 if(demo==='true')return errors // Only an explicitly configured replay build skips live checks.
 const url=text('VITE_SUPABASE_URL'),key=text('VITE_SUPABASE_ANON_KEY'),api=text('VITE_API_BASE_URL')
 if(!url||!validUrl(url,hosted)||url.includes('YOUR_PROJECT'))errors.push('VITE_SUPABASE_URL must contain the Supabase project URL.')
 if(!key||key.includes('YOUR_SUPABASE'))errors.push('VITE_SUPABASE_ANON_KEY must contain a public publishable or anon key.')
 let privateKey=key.startsWith('sb_secret_')
 try{privateKey ||= JSON.parse(atob(key.split('.')[1].replace(/-/g,'+').replace(/_/g,'/'))).role==='service_role'}catch{/* Publishable keys are not JWTs. */}
 if(privateKey)errors.push('VITE_SUPABASE_ANON_KEY must not contain a private secret or service-role key.')
 if((hosted&&!api)||(api&&!validUrl(api,hosted)))errors.push('VITE_API_BASE_URL must contain the backend HTTPS URL for hosted live use; no credentials, query or fragment.')
 return errors
}
