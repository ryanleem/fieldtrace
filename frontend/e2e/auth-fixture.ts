import {expect,type Page} from '@playwright/test'
export const user={id:'10000000-0000-0000-0000-000000000099',aud:'authenticated',role:'authenticated',email:'technician@example.test',app_metadata:{},user_metadata:{},created_at:'2026-01-01T00:00:00Z'}
export function authSession(){
 const exp=Math.floor(Date.now()/1000)+3600
 const token=[{alg:'HS256',typ:'JWT'},{sub:user.id,exp,aud:'authenticated',role:'authenticated'},'test-signature'].map(v=>Buffer.from(JSON.stringify(v)).toString('base64url')).join('.')
 return {access_token:token,refresh_token:'mock-refresh',expires_in:3600,expires_at:exp,token_type:'bearer',user}
}
export async function mockAuth(page:Page,signedIn=true){
 // Only fake auth and local API calls; no Supabase/OpenAI/Gemini traffic leaves tests.
 await page.route('https://**/*',r=>r.abort('blockedbyclient'))
 await page.route('https://auth-fixture.supabase.co/auth/v1/**',r=>{
  const path=new URL(r.request().url()).pathname
  if(path.endsWith('/logout'))return r.fulfill({status:204})
  if(path.endsWith('/user'))return r.fulfill({json:user})
  if(path.endsWith('/signup'))return r.fulfill({json:{user,session:null}})
  return r.fulfill({json:authSession()})
 })
 if(signedIn)await page.addInitScript(({session})=>{if(!sessionStorage.getItem('auth-fixture-seeded')){localStorage.setItem('sb-auth-fixture-auth-token',JSON.stringify(session));sessionStorage.setItem('auth-fixture-seeded','true')}},{session:authSession()})
}
export async function nameSession(page:Page,name='ACS880 Fault 5091'){
 const dialog=page.getByRole('dialog',{name:'Name your troubleshooting session'})
 await expect(dialog).toBeVisible()
 await dialog.getByLabel('Session name').fill(name)
 await dialog.getByRole('button',{name:'Start session',exact:true}).click()
}
