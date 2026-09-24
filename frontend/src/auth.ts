import {createClient} from '@supabase/supabase-js'

const url=import.meta.env.VITE_SUPABASE_URL?.trim()
const key=import.meta.env.VITE_SUPABASE_ANON_KEY?.trim()
// Only a public publishable/anon key belongs in this browser bundle.
export const supabase=url&&key?createClient(url,key,{auth:{persistSession:true,autoRefreshToken:true,detectSessionInUrl:true}}):null

export async function authHeaders(headers?:HeadersInit){
  const result=new Headers(headers)
  if(supabase){
    const {data,error}=await supabase.auth.getSession()
    if(error)throw new Error('Sign-in could not be restored. Please log in again.')
    if(data.session)result.set('Authorization',`Bearer ${data.session.access_token}`)
  }
  return result
}
