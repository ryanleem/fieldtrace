import {expect,it} from 'vitest'
import {liveConfigErrors} from './deploymentConfig'
const valid={VITE_SUPABASE_URL:'https://project.supabase.co',VITE_SUPABASE_ANON_KEY:'sb_publishable_fixture',VITE_API_BASE_URL:'https://backend.example.test',VITE_DEMO_MODE:'false'}
it('accepts complete hosted live configuration',()=>expect(liveConfigErrors(valid,true)).toEqual([]))
for(const name of ['VITE_SUPABASE_URL','VITE_SUPABASE_ANON_KEY','VITE_API_BASE_URL'])it(`rejects missing hosted ${name} without echoing values`,()=>{
 const errors=liveConfigErrors({...valid,[name]:''},true).join(' ')
 expect(errors).toContain(name);expect(errors).not.toContain(valid.VITE_SUPABASE_ANON_KEY)
})
it('missing demo flag defaults to live validation, never replay',()=>expect(liveConfigErrors({},true)).toHaveLength(3))
it('only explicit true allows a standalone replay build',()=>{
 expect(liveConfigErrors({VITE_DEMO_MODE:'true'},true)).toEqual([])
 expect(liveConfigErrors({VITE_DEMO_MODE:'TRUE'},true)).toHaveLength(4)
})
it('local proxy is permitted locally but rejected for hosted builds',()=>{
 expect(liveConfigErrors({...valid,VITE_API_BASE_URL:''},false)).toEqual([])
 expect(liveConfigErrors({...valid,VITE_API_BASE_URL:'/api'},true).join()).toContain('VITE_API_BASE_URL')
})
it('rejects malformed, credential-bearing and non-HTTPS hosted URLs',()=>{
 for(const url of ['invalid','http://backend.example.test','https://user:password@example.test','https://localhost:8000','https://backend.example.test?token=private']){
  const errors=liveConfigErrors({...valid,VITE_API_BASE_URL:url},true).join()
  expect(errors).toContain('VITE_API_BASE_URL');expect(errors).not.toContain(url)
 }
})
it('rejects secret and legacy service-role keys without echoing them',()=>{
 for(const key of ['sb_secret_private-fixture','header.'+btoa(JSON.stringify({role:'service_role'}))+'.signature']){
  const errors=liveConfigErrors({...valid,VITE_SUPABASE_ANON_KEY:key},true).join()
  expect(errors).toContain('private secret or service-role');expect(errors).not.toContain(key)
 }
})
it('accepts legacy public anon keys',()=>expect(liveConfigErrors({...valid,VITE_SUPABASE_ANON_KEY:'header.'+btoa(JSON.stringify({role:'anon'}))+'.signature'},true)).toEqual([]))
