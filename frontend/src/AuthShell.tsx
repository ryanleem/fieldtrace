import {useEffect,useState} from 'react'
import type {Session} from '@supabase/supabase-js'
import {supabase} from './auth'
import App from './App'

export const replayMode=import.meta.env.VITE_DEMO_MODE==='true'||new URLSearchParams(window.location.search).get('demo')==='true'

export default function AuthShell(){
  const [session,setSession]=useState<Session|null>(null),[loading,setLoading]=useState(!replayMode)
  const [signup,setSignup]=useState(false),[email,setEmail]=useState(''),[password,setPassword]=useState('')
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('')
  useEffect(()=>{
    if(replayMode)return
    if(!supabase){setLoading(false);return}
    let active=true,changed=false
    const {data}=supabase.auth.onAuthStateChange((_event,next)=>{changed=true;if(active){setSession(next);setLoading(false)}})
    void supabase.auth.getSession().then(({data,error})=>{if(active&&!changed){setSession(data.session);setLoading(false);if(error)setError('Could not restore sign-in. Please log in again.')}}).catch(()=>{if(active){setLoading(false);setError('Could not restore sign-in. Please log in again.')}})
    return()=>{active=false;data.subscription.unsubscribe()}
  },[])
  async function submit(e:React.FormEvent){
    e.preventDefault();if(!supabase||busy)return
    setBusy(true);setError('');setNotice('')
    try{
      const result=signup?await supabase.auth.signUp({email:email.trim(),password,options:{emailRedirectTo:window.location.origin}}):await supabase.auth.signInWithPassword({email:email.trim(),password})
      if(result.error){setError(signup?'Sign up could not be completed. Check your details or try again later.':'Login failed. Check your email and password or confirm your email first.');return}
      setPassword('');setSession(result.data.session)
      if(!result.data.session)setNotice('Check your email to confirm your account, then log in.')
    }catch{setError('Authentication is unavailable. Please try again later.')}
    finally{setBusy(false)}
  }
  async function logout(){
    if(!supabase)return
    setBusy(true);setError('')
    try{
      const {error}=await supabase.auth.signOut({scope:'local'})
      if(error){setError('Logout failed. Please try again.');return}
      if(session)sessionStorage.removeItem(`fieldtrace.session.${session.user.id}`)
      setSession(null);setPassword('')
    }catch{setError('Logout failed. Please try again.')}
    finally{setBusy(false)}
  }
  if(replayMode)return <App demo userId="replay"/>
  if(loading)return <main><p role="status">Restoring sign-in…</p></main>
  if(session)return <><App key={session.user.id} userId={session.user.id} account={<><span>{session.user.email}</span><button disabled={busy} onClick={()=>void logout()}>Log out</button></>}/>{error&&<p role="alert">{error}</p>}</>
  return <main className="auth-page"><a className="brand" href="/">FieldTrace</a><p className="eyebrow">MAINTENANCE INTELLIGENCE</p><h1>{signup?'Create your account':'Log in to FieldTrace'}</h1><p>Save your equipment investigations and continue with cited ABB evidence.</p>
    {!supabase?<p role="alert">Live sign-in is not configured. The recorded demo is still available.</p>:<form className="panel" onSubmit={submit}>
      <label>Email<input type="email" autoComplete="email" required value={email} onChange={e=>setEmail(e.target.value)}/></label>
      <label>Password<input type="password" autoComplete={signup?'new-password':'current-password'} required minLength={8} value={password} onChange={e=>setPassword(e.target.value)}/></label>
      <button className="primary" disabled={busy}>{busy?'Please wait…':signup?'Sign up':'Log in'}</button>
      <button type="button" className="text-button" disabled={busy} onClick={()=>{setSignup(!signup);setError('');setNotice('')}}>{signup?'Already registered? Log in':'Create an account'}</button>
    </form>}{error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}<a href="/?demo=true">View the labeled recorded demo</a>
  </main>
}
