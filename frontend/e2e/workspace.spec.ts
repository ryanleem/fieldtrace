import {mockAuth,nameSession} from './auth-fixture'
import {test,expect,Page} from '@playwright/test'
import fs from 'node:fs'
import {createHash} from 'node:crypto'
const replay=JSON.parse(fs.readFileSync('public/demo.json','utf8'))
const sid='10000000-0000-0000-0000-000000000001',rid='20000000-0000-0000-0000-000000000001'
export async function mockApi(page:Page,mode='success'){
 await mockAuth(page)
 const eq={...replay.acs880.equipment,session_id:sid,confirmation_status:'UNCONFIRMED',confirmed_equipment_id:null,confirmed_model:null,confidence:null,ranked_candidates:[] as any[]}
 const v={uploaded_images:[] as any[],aggregated_visual_findings:[] as any[],normalized_visual_findings:[]}
 const trace={...structuredClone(replay.acs880.trace),session_id:sid,revision:0,reported_symptoms:[],follow_up_answers:[],checks_completed:[],measurements:[],retrieved_evidence_history:[],result:{...replay.weak.trace.result,status:'not_run',next_question:''}}
 let draft={model:'',symptom:'',followup:'',entry_type:'answer',measurement:{name:'temperature',value:'',unit:'C',location:''}}
 let sessionName='Case'
 const meta=()=>({id:sid,session_id:sid,session_name:sessionName,created_at:new Date().toISOString(),updated_at:new Date().toISOString(),confirmed_model:eq.confirmed_model,symptom_summary:trace.reported_symptoms.join('; '),confidence:trace.result.confidence,result_status:trace.result.status})
 const calls:{path:string;method:string;body:string}[]=[];let failures=mode==='http-failure'?1:0
 await page.route('**/api/**',async route=>{
  const req=route.request(),path=new URL(req.url()).pathname.replace('/api',''),method=req.method(),body=req.postData()||'';calls.push({path,method,body})
  const ok=(data:any)=>route.fulfill({json:data})
  if(path.endsWith('/draft')){if(method==='PUT')draft=JSON.parse(body);return ok(draft)}
  if(path.endsWith('/file'))return route.fulfill({path:'public/replay-photo-01.jpg',contentType:'image/jpeg'})
  if(path.includes('/sources/'))return ok(replay.acs880.source_text[path.split('/').at(-1)!])
  if(path==='/sessions'&&method==='POST'){sessionName=JSON.parse(body).session_name;return ok({...eq,session_name:sessionName})}
  if(path==='/sessions'&&method==='GET')return ok([{...meta(),id:sid}])
  if(path===`/sessions/${sid}`){if(method==='PATCH')sessionName=JSON.parse(body).session_name;return ok(meta())}
  if(path.endsWith('/equipment/identify')){
   eq.ranked_candidates=[{candidate_id:'abb-acs880-01',candidate_model:'ACS880-01',match_level:'HIGH',equipment_family:'ACS880'}];eq.confirmation_status='SUGGESTED';eq.identification_revision=1
   if(mode.startsWith('identity-')){
    const exact=mode==='identity-exact',low=mode==='identity-low'
    Object.assign(eq,{confidence:exact?'HIGH':low?'LOW':'MEDIUM',identification:{specificity:exact?'exact_type':'model_family',label:exact?'ABB ACS880-01-07A2-3':'Likely ABB ACS880 family',confidence:exact?'HIGH':low?'LOW':'MEDIUM',why:exact?'Readable nameplate matches the catalog.':'Visible panel and enclosure cues suggest the family.',to_confirm:'Upload a clear nameplate to confirm the subtype.',exact_type_confirmed:exact}})
    if(!exact)eq.ranked_candidates=[]
   }
   if(mode==='mismatch')eq.mismatch_warnings=['Entered equipment differs from visible nameplate text.']
   return ok(eq)
  }
  if(path.endsWith('/equipment/confirm')){expect(JSON.parse(body).equipment_id).toBe('abb-acs880-01');Object.assign(eq,{confirmation_status:'CONFIRMED',confirmed_equipment_id:'abb-acs880-01',confirmed_model:'ACS880-01',confidence:'HIGH'});return ok(eq)}
  if(path.endsWith('/equipment'))return ok(eq)
  if(path.endsWith('/images')&&method==='POST'){
   const views=JSON.parse(body.match(/name="view_labels"\r\n\r\n([^\r]+)/)?.[1]||'[]')
   const flags=JSON.parse(body.match(/name="identification_flags"\r\n\r\n([^\r]+)/)?.[1]||'[]')
   const notes=JSON.parse(body.match(/name="user_notes"\r\n\r\n([^\r]+)/)?.[1]||'[]')
   const bytes=req.postDataBuffer()!;const marker=bytes.indexOf(Buffer.from('filename='));const start=bytes.indexOf(Buffer.from('\r\n\r\n'),marker)+4;const boundary=req.headers()['content-type'].split('boundary=')[1];const end=bytes.indexOf(Buffer.from('\r\n--'+boundary),start);const digest=createHash('sha256').update(bytes.subarray(start,end)).digest('hex')
   const prior=v.uploaded_images.find(x=>x.content_sha256===digest);if(prior)return ok([prior])
   const items=views.map((view:string,i:number)=>({id:`photo-${v.uploaded_images.length+i}`,equipment_id:eq.confirmed_equipment_id,use_for_identification:flags[i]??view==='nameplate',content_sha256:digest,original_filename:`photo-${i}.jpg`,view_label:view,user_note:notes[i],analysis_status:'pending'}))
   v.uploaded_images.push(...items);return ok(items)
  }
  if(method==='DELETE'&&path.includes('/images/')){const id=path.split('/').at(-1);v.uploaded_images=v.uploaded_images.filter(x=>x.id!==id);v.aggregated_visual_findings=[];return ok({deleted:true,file_cleanup_pending:false})}
  if(path.endsWith('/identification')&&method==='PATCH'){const image=v.uploaded_images.find(x=>path.includes(x.id));Object.assign(image,JSON.parse(body));return ok(image)}
  if(path.endsWith('/images'))return ok(v.uploaded_images)
  if(path.endsWith('/analyze')){
   const image=v.uploaded_images.find(x=>path.includes(x.id));image.analysis_status=mode==='vision-failure'?'failed':'completed'
   if(mode!=='vision-failure')v.aggregated_visual_findings=[{id:'f1',equipment_id:eq.confirmed_equipment_id,supporting_image_ids:v.uploaded_images.map(x=>x.id),issue_type:'corrosion',location:'contacts',description:'Visible corrosion on contacts.',visual_confidence:'high',severity:'medium'}]
   return ok({image,findings:[]})
  }
  if(path.endsWith('/visual-findings'))return ok(v)
  if(path.endsWith('/symptoms')){trace.reported_symptoms.push(JSON.parse(body).symptom);trace.revision++;trace.result={...replay.weak.trace.result,status:'not_run',next_question:''};return ok(trace)}
  if(path.endsWith('/run')||path.endsWith('/follow-up')){
   if(path.endsWith('/follow-up')){const data=JSON.parse(body);if(data.answer)trace.follow_up_answers.push(data.answer);if(data.checks_completed)trace.checks_completed.push(...data.checks_completed);if(data.measurements)trace.measurements.push(...data.measurements);trace.revision++}
   if(failures-->0)return route.fulfill({status:503,json:{detail:'unavailable'}})
   trace.result=structuredClone(mode==='weak'?replay.weak.trace.result:replay.acs880.trace.result)
   if(mode==='provider-failure')trace.result={...replay.weak.trace.result,status:'failed'}
   if(mode==='conflict')trace.result.conflicts=[{relationship:'DIFFERENT_APPLICABILITY',citation_chunk_ids:trace.result.sources.slice(0,2).map((s:any)=>s.chunk_id)}]
   trace.retrieved_evidence_history.push({run_id:`${rid}-${trace.retrieved_evidence_history.length}`,status:trace.result.status,created_at:new Date().toISOString(),sources:trace.result.sources})
   return ok(trace)
  }
  if(path.endsWith('/troubleshooting'))return ok(trace)
  throw new Error('Unhandled mock route '+method+' '+path)
 })
 return {calls,trace,v}
}
async function confirm(page:Page){
 await page.getByRole('button',{name:'Start new troubleshooting session'}).click();await nameSession(page)
 await page.getByLabel('Model text, if known').fill('ABB ACS880-01')
 await page.getByRole('button',{name:'Detect equipment / read nameplate'}).click()
 await page.getByRole('button',{name:'Confirm equipment',exact:true}).click()
 await expect(page.getByText('CONFIRMED EQUIPMENT',{exact:true})).toBeVisible()
}
test('fresh workspace is locked until explicitly named',async({page})=>{
 const mock=await mockApi(page);await page.goto('/')
 await expect(page.getByRole('heading',{name:'No active troubleshooting session'})).toBeVisible()
 for(const label of ['Add equipment photos','Model text, if known','What problem are you seeing?'])await expect(page.getByLabel(label,{exact:true})).toBeDisabled()
 for(const name of ['Detect equipment / read nameplate','Run troubleshooting'])await expect(page.getByRole('button',{name})).toBeDisabled()
 expect(mock.calls).toHaveLength(0)
 await page.getByRole('button',{name:'Start new troubleshooting session'}).click()
 await page.getByRole('button',{name:'Cancel',exact:true}).click()
 await expect(page.getByLabel('Model text, if known')).toBeDisabled();expect(mock.calls).toHaveLength(0)
 await page.getByRole('button',{name:'Start new troubleshooting session'}).click();await nameSession(page)
 await expect(page.getByRole('heading',{name:'ACS880 Fault 5091',exact:true})).toBeVisible()
 for(const label of ['Add equipment photos','Model text, if known','What problem are you seeing?'])await expect(page.getByLabel(label,{exact:true})).toBeEnabled()
 expect(mock.calls.filter(c=>c.method==='POST')).toHaveLength(1)
 await expect(page.getByRole('button',{name:'Run troubleshooting'})).toBeDisabled()
})

test('failed named creation stays locked and can retry',async({page})=>{
 const mock=await mockApi(page);let creations=0
 await page.route('**/api/sessions',route=>++creations===1?route.fulfill({status:503,json:{detail:'unavailable'}}):route.fallback())
 await page.goto('/')
 await page.getByRole('button',{name:'Start new troubleshooting session'}).click();await nameSession(page)
 await expect(page.getByRole('alert')).toBeVisible();await expect(page.getByLabel('Model text, if known')).toBeDisabled()
 await page.getByRole('button',{name:'Start new troubleshooting session'}).click();await nameSession(page)
 await expect(page.getByLabel('Model text, if known')).toBeEnabled();expect(creations).toBe(2)
 expect(mock.calls.some(c=>c.path.includes('/identify'))).toBe(false)
})

test('concurrent start clicks create exactly one named session',async({page})=>{
 const mock=await mockApi(page);await page.goto('/')
 await page.getByRole('button',{name:'Start new troubleshooting session'}).evaluate((button:HTMLButtonElement)=>{button.click();button.click()})
 await nameSession(page)
 await expect(page.getByLabel('Model text, if known')).toBeEnabled()
 expect(mock.calls.filter(c=>c.path==='/sessions'&&c.method==='POST')).toHaveLength(1)
})

test('new case cancellation preserves the active case and drafts',async({page})=>{
 await mockApi(page);await page.goto('/');await confirm(page)
 await page.getByLabel('What problem are you seeing?').fill('Fault 5091')
 await page.getByRole('button',{name:'Start new troubleshooting session'}).click()
 await page.getByRole('button',{name:'Cancel',exact:true}).click()
 await expect(page.getByLabel('What problem are you seeing?')).toHaveValue('Fault 5091')
 await expect(page.getByRole('heading',{name:'ACS880 Fault 5091',exact:true})).toBeVisible()
 await page.getByRole('button',{name:'Start new troubleshooting session'}).click();await nameSession(page,'New case')
 await expect(page.getByLabel('What problem are you seeing?')).toHaveValue('')
 await expect(page.getByRole('heading',{name:'New case',exact:true})).toBeVisible()
})

test('complete multi-photo, identification, result, citation and follow-up workflow',async({page})=>{
 const mock=await mockApi(page);await page.goto('/')
 await page.getByRole('button',{name:'Start new troubleshooting session'}).click();await nameSession(page)
 await expect(page.getByLabel('Add equipment photos',{exact:true})).toBeEnabled()
 await page.getByLabel('Add equipment photos',{exact:true}).setInputFiles([
  {name:'front.jpg',mimeType:'image/jpeg',buffer:fs.readFileSync('public/replay-photo-01.jpg')},
  {name:'nameplate.jpg',mimeType:'image/jpeg',buffer:Buffer.concat([fs.readFileSync('public/replay-photo-01.jpg'),Buffer.from('different angle')])}])
 await page.getByLabel('View for front.jpg').selectOption('front');await page.getByLabel('View for nameplate.jpg').selectOption('nameplate')
 await page.getByLabel('Photo note').first().fill('Noise was heard here')
 await page.getByLabel('Model text, if known').fill('ACS880-01')
 await page.getByRole('button',{name:'Detect equipment / read nameplate'}).click()
 await page.getByRole('button',{name:'Confirm equipment',exact:true}).click()
 await expect(page.getByText('Noise was heard here',{exact:false}).first()).toBeVisible()
 await page.getByRole('button',{name:'Save photos & inspect visible conditions'}).click()
 await expect(page.getByText('Visible corrosion on contacts.')).toBeVisible()
 expect(mock.v.uploaded_images.map(x=>x.view_label)).toEqual(['front','nameplate'])
 await page.getByLabel('What problem are you seeing?').fill('Drive shows fault 5091')
 await page.getByRole('button',{name:'Run troubleshooting',exact:false}).click()
 await expect(page.getByRole('heading',{name:replay.acs880.trace.result.primary_cause.label,exact:true})).toBeVisible()
 await expect(page.getByText('MEDIUM',{exact:true})).toBeVisible()
 await page.getByRole('button',{name:/↗ ACS880.*p.525/}).first().click()
 await expect(page.getByRole('dialog')).toBeVisible();await expect(page.getByText('Exact cited chunk',{exact:true})).toBeVisible()
 await expect(page.locator('.excerpt')).toContainText('5091')
 await expect(page.getByRole('link',{name:'Open manual page'})).toHaveAttribute('href',/#page=525/)
 await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).not.toBeVisible()
 const upstream=mock.calls.filter(x=>/identify|analyze/.test(x.path)).length
 await page.getByLabel('Update for this session').fill('The cooling fan is running.')
 await page.getByRole('button',{name:'Submit update & check documentation'}).click()
 await expect(page.getByText('Follow-up saved: The cooling fan is running.')).toBeVisible()
 expect(mock.calls.filter(x=>/identify|analyze/.test(x.path)).length).toBe(upstream)
 expect(mock.trace.follow_up_answers).toEqual(['The cooling fan is running.'])
 await page.screenshot({path:'test-results/workspace-success.png',fullPage:true})
 await page.reload();await expect(page.getByText('Follow-up saved: The cooling fan is running.')).toBeVisible()
})
test('weak evidence stays a normal LOW workflow without a forced diagnosis',async({page})=>{
 await mockApi(page,'weak');await page.goto('/');await confirm(page)
 await page.getByLabel('What problem are you seeing?').fill('Something seems wrong')
 await page.getByRole('button',{name:'Run troubleshooting'}).click()
 await expect(page.getByRole('heading',{name:'We need more information before narrowing this down.'})).toBeVisible()
 await expect(page.getByText('LOW',{exact:true})).toBeVisible()
 await expect(page.locator('.cause-title')).toHaveCount(0)
 await expect(page.locator('.next-question')).toContainText(replay.weak.trace.result.next_question)
})
test('conflicting applicability is visible with linked sources',async({page})=>{
 await mockApi(page,'conflict');await page.goto('/');await confirm(page)
 await page.getByLabel('What problem are you seeing?').fill('Fault 5091')
 await page.getByRole('button',{name:'Run troubleshooting'}).click()
 await expect(page.getByRole('heading',{name:'Some source guidance differs.'})).toBeVisible()
 await expect(page.locator('.conflict .source-chip')).toHaveCount(2)
})
test('transport failure preserves session and symptom, refresh then retry succeeds',async({page})=>{
 const mock=await mockApi(page,'http-failure');await page.goto('/');await confirm(page)
 await page.getByLabel('What problem are you seeing?').fill('Fault 5091')
 await page.getByRole('button',{name:'Run troubleshooting'}).click()
 await expect(page.getByRole('alert')).toContainText('temporarily unavailable')
 await expect(page.getByLabel('What problem are you seeing?')).toHaveValue('Fault 5091')
 expect(await page.evaluate(()=>sessionStorage.getItem('fieldtrace.session.10000000-0000-0000-0000-000000000099'))).toBe(sid)
 await page.getByRole('button',{name:'Refresh session status'}).click()
 await page.getByRole('button',{name:'Run troubleshooting'}).click()
 await expect(page.locator('.cause-title')).toBeVisible();expect(mock.trace.reported_symptoms).toContain('Fault 5091')
})
test('provider failure is not disguised as a low-evidence success',async({page})=>{
 await mockApi(page,'provider-failure');await page.goto('/');await confirm(page)
 await page.getByLabel('What problem are you seeing?').fill('Fault 5091');await page.getByRole('button',{name:'Run troubleshooting'}).click()
 await expect(page.getByRole('heading',{name:'Troubleshooting service unavailable'})).toBeVisible()
 await expect(page.locator('.result-title .badge')).toHaveCount(0)
 await expect(page.getByRole('button',{name:'Retry troubleshooting'})).toBeVisible();await expect(page.locator('.cause-title')).toHaveCount(0)
})

for(const [label,status] of [['quota / rate limit',429],['database unavailable',503],['retrieval exception',500],['provider timeout',504]] as const){
 test(`${label} preserves inputs and allows retry`,async({page})=>{
  await mockApi(page);let first=true
  await page.route('**/troubleshooting/run',route=>{if(first){first=false;return route.fulfill({status,json:{detail:'failure fixture'}})}return route.fallback()})
  await page.goto('/');await confirm(page);await page.getByLabel('What problem are you seeing?').fill('Fault 5091')
  await page.getByRole('button',{name:'Run troubleshooting'}).click()
  await expect(page.getByRole('alert')).toBeVisible();await expect(page.locator('.cause-title')).toHaveCount(0)
  await expect(page.getByLabel('What problem are you seeing?')).toHaveValue('Fault 5091')
  expect(await page.evaluate(()=>sessionStorage.getItem('fieldtrace.session.10000000-0000-0000-0000-000000000099'))).toBe(sid)
  await page.getByRole('button',{name:'Run troubleshooting'}).click();await expect(page.locator('.cause-title')).toBeVisible()
 })
}

test('backend disconnect keeps the confirmed session and offers refresh',async({page})=>{
 await mockApi(page);await page.goto('/');await confirm(page)
 await page.route('**/troubleshooting/run',r=>r.abort('connectionrefused'))
 await page.getByLabel('What problem are you seeing?').fill('Fault 5091');await page.getByRole('button',{name:'Run troubleshooting'}).click()
 await expect(page.getByRole('alert')).toContainText('Cannot reach the backend')
 await expect(page.getByRole('button',{name:'Refresh session status'})).toBeVisible()
 await expect(page.getByText('CONFIRMED EQUIPMENT',{exact:true})).toBeVisible()
})

test('corrupt image rejection retains the queued photo and does not run vision',async({page})=>{
 const mock=await mockApi(page);await page.goto('/');await confirm(page)
 await page.route('**/images',r=>r.request().method()==='POST'?r.fulfill({status:422,json:{detail:'Image is corrupt or unreadable'}}):r.fallback())
 await page.getByLabel('Add equipment photos',{exact:true}).setInputFiles({name:'broken.jpg',mimeType:'image/jpeg',buffer:Buffer.from('not an image')})
 await page.getByRole('button',{name:'Save photos & inspect visible conditions'}).click()
 await expect(page.getByRole('alert')).toContainText('corrupt or unreadable');await expect(page.locator('.pending-photo')).toHaveCount(1)
 expect(mock.calls.filter(c=>c.path.endsWith('/analyze'))).toHaveLength(0)
})

test('new session clears result, photos, follow-up and measurement draft',async({page})=>{
 await mockApi(page);await page.goto('/');await confirm(page)
 await page.getByLabel('What problem are you seeing?').fill('Fault 5091');await page.getByRole('button',{name:'Run troubleshooting'}).click()
 await page.getByLabel('Update for this session').fill('old answer');await page.getByLabel('Entry type').selectOption('measurement')
 await page.getByLabel('value',{exact:true}).fill('92')
 await page.getByLabel('Add equipment photos',{exact:true}).setInputFiles('public/replay-photo-01.jpg')
 await page.getByRole('button',{name:'Start new troubleshooting session'}).click();await nameSession(page)
 await expect(page.locator('.cause-title')).toHaveCount(0);await expect(page.locator('.pending-photo')).toHaveCount(0)
 await expect(page.getByLabel('What problem are you seeing?')).toHaveValue('')
 await page.getByLabel('Model text, if known').fill('ACS880-01');await page.getByRole('button',{name:'Correct equipment',exact:true}).click()
 await page.getByRole('button',{name:'Confirm equipment',exact:true}).click()
 await page.getByLabel('What problem are you seeing?').fill('Fault 5091');await page.getByRole('button',{name:'Run troubleshooting'}).click()
 await expect(page.getByLabel('Entry type')).toHaveValue('answer');await expect(page.getByLabel('Update for this session')).toHaveValue('')
 await page.getByLabel('Entry type').selectOption('measurement');await expect(page.getByLabel('value',{exact:true})).toHaveValue('')
})
test('vision failure retains photo and offers retry without fake findings',async({page})=>{
 await mockApi(page,'vision-failure');await page.goto('/');await confirm(page)
 await page.getByLabel('Add equipment photos',{exact:true}).setInputFiles('public/replay-photo-01.jpg')
 await page.getByRole('button',{name:'Save photos & inspect visible conditions'}).click()
 await expect(page.getByRole('alert')).toContainText('Some photos could not be analyzed')
 await expect(page.locator('.saved-photos img')).toHaveCount(1);await expect(page.locator('.finding')).toHaveCount(0)
 await expect(page.getByRole('button',{name:'Save photos & inspect visible conditions'})).toBeEnabled()
})
test('mismatch warning and responsive intake remain usable',async({page})=>{
 await page.setViewportSize({width:390,height:844});await mockApi(page,'mismatch');await page.goto('/')
 await page.getByRole('button',{name:'Start new troubleshooting session'}).click();await nameSession(page);await page.getByLabel('Model text, if known').fill('ACS580-01')
 await page.getByRole('button',{name:'Detect equipment / read nameplate'}).click()
 if(await page.getByRole('dialog',{name:'Name your troubleshooting session'}).isVisible())await nameSession(page)
 await expect(page.getByText('Entered equipment differs from visible nameplate text.')).toBeVisible()
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true)
 await expect(page.getByRole('button',{name:'Run troubleshooting'})).toBeDisabled()
})


test('My Sessions reopens, renames and refreshes without provider calls',async({page})=>{
 const mock=await mockApi(page);await page.goto('/');await confirm(page)
 await page.getByLabel('What problem are you seeing?').fill('Fault 5091');await page.getByRole('button',{name:'Run troubleshooting'}).click()
 await expect(page.locator('.cause-title')).toBeVisible()
 const initial=mock.calls.filter(c=>c.method!=='GET').length
 await page.getByRole('button',{name:'My Sessions',exact:true}).click()
 await expect(page.locator('.session-card')).toContainText('ACS880 Fault 5091')
 await page.getByRole('button',{name:'Rename',exact:true}).click()
 await page.getByRole('dialog',{name:'Rename session'}).getByLabel('Session name').fill('Drive cabinet follow-up')
 await page.getByRole('button',{name:'Save name'}).click()
 await expect(page.locator('.session-card')).toContainText('Drive cabinet follow-up')
 await page.getByRole('button',{name:'Workspace',exact:true}).click()
 await expect(page.getByRole('heading',{name:'Drive cabinet follow-up',exact:true})).toBeVisible()
 await page.getByRole('button',{name:'My Sessions',exact:true}).click()
 await page.getByRole('button',{name:'Continue troubleshooting'}).click()
 await expect(page.locator('.cause-title')).toBeVisible();await expect(page.locator('.session-status')).toContainText('Drive cabinet follow-up')
 await page.reload();await expect(page.locator('.cause-title')).toBeVisible()
 expect(mock.calls.filter(c=>c.method!=='GET').length).toBe(initial+1) // rename only
 await page.getByRole('button',{name:'Log out'}).click();await expect(page.getByRole('heading',{name:'Log in to FieldTrace'})).toBeVisible()
 await expect(page.locator('.cause-title')).toHaveCount(0)
})

test('inaccessible saved session is cleared without exposing another account',async({page})=>{
 await mockApi(page)
 await page.addInitScript(()=>sessionStorage.setItem('fieldtrace.session.10000000-0000-0000-0000-000000000099','foreign-case'))
 await page.route('**/api/sessions/foreign-case**',r=>r.fulfill({status:404,json:{detail:'Session not found'}}))
 await page.goto('/');await expect(page.getByRole('alert')).toContainText('unavailable for this account')
 await expect(page.locator('.session-status')).toContainText('No active session')
 await expect(page.locator('.cause-title')).toHaveCount(0)
})

test('opening saved case unlocks workspace without provider calls',async({page})=>{
 const mock=await mockApi(page);await page.goto('/')
 await page.getByRole('button',{name:'My Sessions',exact:true}).click()
 await page.getByRole('button',{name:'Continue troubleshooting'}).click()
 await expect(page.getByRole('heading',{name:'Case',exact:true})).toBeVisible()
 await expect(page.getByLabel('Model text, if known')).toBeEnabled()
 expect(mock.calls.every(c=>c.method==='GET')).toBe(true)
})


test('delete confirmation cancels, fails safely, then deletes active case once',async({page})=>{
 const mock=await mockApi(page);await page.goto('/');await confirm(page)
 await page.getByRole('button',{name:'My Sessions',exact:true}).click()
 await page.getByRole('button',{name:'Delete',exact:true}).click()
 await expect(page.getByRole('dialog',{name:'Delete troubleshooting session?'})).toContainText('ACS880 Fault 5091')
 await page.getByRole('button',{name:'Cancel',exact:true}).click()
 expect(mock.calls.filter(c=>c.method==='DELETE')).toHaveLength(0)
 await expect(page.locator('.session-card')).toHaveCount(1)
 let deletes=0
 await page.route(`**/api/sessions/${sid}`,r=>{
  if(r.request().method()!=='DELETE')return r.fallback()
  deletes++;return deletes===1?r.fulfill({status:404,json:{detail:'Session not found'}}):r.fulfill({json:{deleted:true,file_cleanup_pending:false}})
 })
 await page.getByRole('button',{name:'Delete',exact:true}).click()
 await page.getByRole('button',{name:'Delete session',exact:true}).click()
 await expect(page.getByRole('alert')).toContainText('unavailable for this account')
 await expect(page.locator('.session-card')).toHaveCount(1)
 await page.getByRole('button',{name:'Delete',exact:true}).click()
 await page.getByRole('button',{name:'Delete session',exact:true}).evaluate((button:HTMLButtonElement)=>{button.click();button.click()})
 await expect(page.getByRole('heading',{name:'No active troubleshooting session'})).toBeVisible()
 await expect(page.getByLabel('Model text, if known')).toBeDisabled()
 await expect(page.locator('.session-card')).toHaveCount(0)
 await expect(page.getByText('Session deleted.',{exact:true})).toBeVisible()
 expect(deletes).toBe(2)
 expect(await page.evaluate(()=>sessionStorage.getItem('fieldtrace.session.10000000-0000-0000-0000-000000000099'))).toBeNull()
})


test('draft autosave restores on refresh and reopen; manual failure retries without losing text',async({page})=>{
 const mock=await mockApi(page);await page.goto('/')
 await expect(page.getByRole('button',{name:'Save',exact:true})).toHaveCount(0)
 await page.getByRole('button',{name:'Start new troubleshooting session'}).click();await nameSession(page)
 await page.getByLabel('Model text, if known').fill('ABB ACS880-01')
 await page.getByLabel('What problem are you seeing?').fill('Draft fault 5091')
 await expect.poll(()=>mock.calls.filter(c=>c.path.endsWith('/draft')&&c.method==='PUT').length).toBe(1)
 await expect(page.locator('.save-controls [role=status]')).toHaveCount(0)
 await page.reload();await expect(page.getByLabel('What problem are you seeing?')).toHaveValue('Draft fault 5091')
 await page.getByRole('button',{name:'My Sessions',exact:true}).click()
 await page.getByRole('button',{name:'Continue troubleshooting'}).click()
 await expect(page.getByLabel('Model text, if known')).toHaveValue('ABB ACS880-01')
 await expect(page.getByLabel('What problem are you seeing?')).toHaveValue('Draft fault 5091')
 let failures=1
 await page.route('**/api/sessions/*/draft',r=>r.request().method()==='PUT'&&failures-->0?r.fulfill({status:503,json:{detail:'unavailable'}}):r.fallback())
 await page.getByLabel('What problem are you seeing?').fill('Keep this draft')
 await page.getByRole('button',{name:'Save',exact:true}).click()
 await expect(page.locator('.save-controls')).toContainText('Save failed')
 await expect(page.getByLabel('What problem are you seeing?')).toHaveValue('Keep this draft')
 await page.getByRole('button',{name:'Save',exact:true}).click()
 await expect(page.locator('.save-controls')).toContainText('Saved successfully')
 expect(mock.calls.filter(c=>c.method!=='GET'&&!c.path.endsWith('/draft')&&c.path!=='/sessions')).toHaveLength(0)
})

test('manual Save disables during request and text saving never duplicates photos',async({page})=>{
 const mock=await mockApi(page);await page.goto('/');await confirm(page)
 await page.getByLabel('Add equipment photos',{exact:true}).setInputFiles('public/replay-photo-01.jpg')
 await page.getByRole('button',{name:'Save photos without analysis',exact:true}).click()
 await expect(page.locator('.saved-photos img')).toHaveCount(1)
 let release!:()=>void;const held=new Promise<void>(r=>{release=r})
 await page.route('**/api/sessions/*/draft',async r=>{if(r.request().method()==='PUT')await held;await r.fallback()})
 await page.getByLabel('What problem are you seeing?').fill('Saved symptom')
 await page.getByRole('button',{name:'Save',exact:true}).click()
 await expect(page.getByRole('button',{name:'Save',exact:true})).toBeDisabled()
 await expect(page.locator('.save-controls')).not.toContainText('Saved successfully')
 release();await expect(page.locator('.save-controls')).toContainText('Saved successfully')
 expect(mock.calls.filter(c=>c.path.endsWith('/images')&&c.method==='POST')).toHaveLength(1)
 expect(mock.calls.some(c=>c.path.endsWith('/analyze')||c.path.endsWith('/run'))).toBe(false)
})


test('main Save uploads queue, retains partial failures and retries only unsaved files',async({page})=>{
 const mock=await mockApi(page);await page.goto('/')
 await page.getByRole('button',{name:'Start new troubleshooting session'}).click();await nameSession(page)
 await expect(page.locator('.heading-actions').getByRole('button',{name:'Save',exact:true})).toBeVisible()
 await expect(page.locator('.heading-actions').getByRole('button',{name:'Start new troubleshooting session'})).toBeVisible()
 await page.getByLabel('Add equipment photos',{exact:true}).setInputFiles([
  {name:'one.jpg',mimeType:'image/jpeg',buffer:fs.readFileSync('public/replay-photo-01.jpg')},
  {name:'two.jpg',mimeType:'image/jpeg',buffer:Buffer.concat([fs.readFileSync('public/replay-photo-01.jpg'),Buffer.from('second')])}])
 let uploads=0
 await page.route('**/api/sessions/*/images',r=>{
  if(r.request().method()!=='POST')return r.fallback()
  uploads++;return uploads===2?r.fulfill({status:503,json:{detail:'unavailable'}}):r.fallback()
 })
 await page.getByRole('button',{name:'Save',exact:true}).evaluate((button:HTMLButtonElement)=>{button.click();button.click()})
 await expect(page.locator('.save-controls')).toContainText('Save failed')
 await expect(page.locator('.pending-photo')).toHaveCount(1)
 await expect(page.locator('.pending-photo')).toContainText('two.jpg')
 await expect(page.locator('.saved-photos img')).toHaveCount(1)
 await page.getByRole('button',{name:'Save',exact:true}).click()
 await expect(page.locator('.save-controls')).toContainText('Saved successfully')
 await expect(page.locator('.pending-photo')).toHaveCount(0)
 await expect(page.locator('.saved-photos img')).toHaveCount(2)
 expect(uploads).toBe(3)
 await expect(page.getByText('Saved successfully',{exact:true})).toHaveCount(0,{timeout:4000})
 await page.getByRole('button',{name:'Save',exact:true}).click()
 await expect(page.getByText('Saved successfully',{exact:true})).toBeVisible()
 expect(uploads).toBe(3)
 expect(mock.calls.some(c=>/identify|analyze|follow-up|\/run/.test(c.path))).toBe(false)
})


test('manual upload blocks switching and logout stops remaining queued uploads',async({page})=>{
 await mockApi(page);await page.goto('/')
 await page.getByRole('button',{name:'Start new troubleshooting session'}).click();await nameSession(page)
 await expect(page.getByLabel('Add equipment photos',{exact:true})).toBeEnabled()
 await page.getByLabel('Add equipment photos',{exact:true}).setInputFiles([
  {name:'one.jpg',mimeType:'image/jpeg',buffer:fs.readFileSync('public/replay-photo-01.jpg')},
  {name:'two.jpg',mimeType:'image/jpeg',buffer:Buffer.concat([fs.readFileSync('public/replay-photo-01.jpg'),Buffer.from('second')])}])
 let uploads=0,release!:()=>void;const held=new Promise<void>(r=>{release=r})
 await page.route('**/api/sessions/*/images',async r=>{if(r.request().method()==='POST'){uploads++;await held};await r.fallback()})
 await page.getByRole('button',{name:'Save',exact:true}).click()
 await expect.poll(()=>uploads).toBe(1)
 await expect(page.locator('.pending-photo').first()).toContainText('Uploading')
 await expect(page.getByRole('button',{name:'My Sessions',exact:true})).toBeDisabled()
 await expect(page.getByRole('button',{name:'Start new troubleshooting session'})).toBeDisabled()
 await page.getByRole('button',{name:'Log out',exact:true}).click()
 await expect(page.getByRole('heading',{name:'Log in to FieldTrace'})).toBeVisible()
 const response=page.waitForResponse(r=>r.url().endsWith('/images')&&r.request().method()==='POST')
 release();await response
 await expect(page.getByRole('button',{name:'Save',exact:true})).toHaveCount(0)
 expect(uploads).toBe(1)
})


test('content duplicates are skipped, different bytes and latest notes persist without analysis',async({page})=>{
 const mock=await mockApi(page);await page.goto('/');await confirm(page)
 const file={name:'same.jpg',mimeType:'image/jpeg',buffer:fs.readFileSync('public/replay-photo-01.jpg')}
 const picker=page.getByLabel('Add equipment photos',{exact:true})
 await picker.setInputFiles([file,file]);await expect(page.locator('.pending-photo')).toHaveCount(1)
 await expect(page.getByText('same.jpg is already attached to this session.')).toBeVisible()
 await picker.setInputFiles({...file,buffer:Buffer.concat([file.buffer,Buffer.from('different bytes')])})
 await expect(page.locator('.pending-photo')).toHaveCount(2)
 await page.getByLabel('Photo note',{exact:true}).first().fill('Latest technician note')
 await page.getByRole('button',{name:'Save',exact:true}).click()
 await expect(page.locator('.pending-photo')).toHaveCount(0)
 await expect(page.getByText('Saved · Not analyzed',{exact:true})).toHaveCount(2)
 expect(mock.v.uploaded_images[0].user_note).toBe('Latest technician note')
 await picker.setInputFiles(file);await expect(page.getByText('same.jpg is already attached to this session.')).toBeVisible()
 await expect(page.locator('.pending-photo')).toHaveCount(0)
 await page.getByRole('button',{name:'Save',exact:true}).click()
 expect(mock.calls.filter(c=>c.method==='POST'&&c.path.endsWith('/images'))).toHaveLength(2)
 expect(mock.calls.some(c=>c.path.endsWith('/analyze'))).toBe(false)
})

test('saved photo analysis is explicit and confirmed removal preserves other photos',async({page})=>{
 const mock=await mockApi(page);await page.goto('/');await confirm(page)
 const bytes=fs.readFileSync('public/replay-photo-01.jpg')
 await page.getByLabel('Add equipment photos',{exact:true}).setInputFiles([
 {name:'one.jpg',mimeType:'image/jpeg',buffer:bytes},{name:'two.jpg',mimeType:'image/jpeg',buffer:Buffer.concat([bytes,Buffer.from('other')])}])
 await expect(page.locator('.pending-photo')).toHaveCount(2)
 await page.getByRole('button',{name:'Save',exact:true}).click()
 await expect(page.getByText('Saved · Not analyzed',{exact:true})).toHaveCount(2)
 await page.getByRole('button',{name:'Inspect / Analyze',exact:true}).first().click()
 await expect(page.getByText('Analysis complete',{exact:true})).toHaveCount(1)
 await page.getByRole('button',{name:'Remove',exact:true}).first().click()
 await expect(page.getByRole('dialog')).toContainText('saved visual findings')
 await page.getByRole('button',{name:'Cancel',exact:true}).click()
 expect(mock.calls.filter(c=>c.method==='DELETE')).toHaveLength(0)
 await expect(page.locator('.saved-photos figure')).toHaveCount(2)
 await page.getByRole('button',{name:'Remove',exact:true}).first().click()
 await page.getByRole('button',{name:'Remove photo',exact:true}).evaluate((b:HTMLButtonElement)=>{b.click();b.click()})
 await expect(page.locator('.saved-photos figure')).toHaveCount(1)
 expect(mock.calls.filter(c=>c.method==='DELETE')).toHaveLength(1)
 expect(mock.v.aggregated_visual_findings).toHaveLength(0)
})


test('failed saved-photo removal keeps the photo and shows a safe error',async({page})=>{
 await mockApi(page);await page.goto('/');await confirm(page)
 await page.getByLabel('Add equipment photos',{exact:true}).setInputFiles({name:'keep.jpg',mimeType:'image/jpeg',buffer:fs.readFileSync('public/replay-photo-01.jpg')})
 await expect(page.locator('.pending-photo')).toHaveCount(1)
 await page.getByRole('button',{name:'Save',exact:true}).click()
 await expect(page.locator('.saved-photos figure')).toHaveCount(1)
 await page.route('**/images/photo-*',r=>r.request().method()==='DELETE'?r.fulfill({status:404,json:{detail:'Session not found'}}):r.fallback())
 await page.getByRole('button',{name:'Remove',exact:true}).click()
 await page.getByRole('button',{name:'Remove photo',exact:true}).click()
 await expect(page.getByRole('alert')).toBeVisible()
 await expect(page.locator('.saved-photos figure')).toHaveCount(1)
})


test('equipment photos stay in step one and vague symptoms are excluded from identification',async({page})=>{
 const mock=await mockApi(page);await page.goto('/')
 await page.getByRole('button',{name:'Start new troubleshooting session'}).click();await nameSession(page)
 const intake=page.locator('section.panel').filter({has:page.getByRole('heading',{name:'Equipment & photos',exact:true})})
 await expect(intake.getByLabel('Add equipment photos',{exact:true})).toBeVisible()
 await expect(intake.getByRole('button',{name:'Save photos & inspect visible conditions'})).toBeVisible()
 const problem=page.locator('section.panel').filter({has:page.getByRole('heading',{name:'What’s happening',exact:true})})
 await expect(problem.getByLabel('What problem are you seeing?')).toBeVisible()
 await expect(problem.getByRole('button',{name:'Save photos & inspect visible conditions'})).toHaveCount(0)
 await page.getByLabel('What problem are you seeing?').fill('not sure')
 await page.getByLabel('Add equipment photos',{exact:true}).setInputFiles({name:'plate.jpg',mimeType:'image/jpeg',buffer:fs.readFileSync('public/replay-photo-01.jpg')})
 await page.getByLabel('View for plate.jpg').selectOption('nameplate')
 await intake.getByRole('button',{name:'Save photos & inspect visible conditions'}).click()
 await expect(page.getByRole('button',{name:'Confirm equipment',exact:true})).toBeVisible()
 const call=mock.calls.find(c=>c.path.endsWith('/equipment/identify'))!
 expect(call.body).not.toContain('not sure');expect(call.body).toContain('nameplate')
 await page.getByRole('button',{name:'Confirm equipment',exact:true}).click()
 await expect(page.getByRole('button',{name:'Correct equipment',exact:true})).toBeVisible()
 await expect(page.getByRole('button',{name:'Re-detect / correct equipment'})).toHaveCount(0)
})

for(const kind of ['answer','check','measurement'])test(`follow-up ${kind} is recorded, refreshed and explains unchanged guidance`,async({page})=>{
 const mock=await mockApi(page);await page.goto('/');await confirm(page)
 await page.getByLabel('What problem are you seeing?').fill('Fault 5091')
 await page.getByRole('button',{name:'Run troubleshooting'}).click()
 await expect(page.getByRole('heading',{name:'Why this matches'})).toBeVisible()
 await expect(page.getByRole('heading',{name:'What to check next'})).toBeVisible()
 await expect(page.locator('.rationale .source-chip').first()).toBeVisible()
 const value='STO wiring has not yet been checked.'
 await page.getByLabel('Entry type').selectOption(kind)
 if(kind==='measurement')await page.getByLabel('value',{exact:true}).fill('42')
 else await page.getByLabel('Update for this session').fill(value)
 await page.getByRole('button',{name:'Submit update & check documentation'}).click()
 await expect(page.getByText('Update saved. No new troubleshooting guidance was found from this information.',{exact:true})).toBeVisible()
 if(kind==='measurement'){
  expect(mock.trace.measurements[0].value).toBe('42');await expect(page.getByLabel('value',{exact:true})).toHaveValue('')
  await expect(page.locator('.history')).toContainText('Measurement: temperature 42 C')
 }else{
  expect(kind==='answer'?mock.trace.follow_up_answers:mock.trace.checks_completed).toContain(value)
  await expect(page.getByLabel('Update for this session')).toHaveValue('')
  await expect(page.locator('.history')).toContainText(value)
 }
 await page.reload();await expect(page.locator('.history')).toContainText(kind==='measurement'?'temperature 42 C':value)
 expect(mock.calls.filter(c=>c.path.endsWith('/follow-up'))).toHaveLength(1)
})

test('follow-up failure retains the entry and displays an error without a stuck spinner',async({page})=>{
 await mockApi(page);await page.goto('/');await confirm(page)
 await page.getByLabel('What problem are you seeing?').fill('5091');await page.getByRole('button',{name:'Run troubleshooting'}).click()
 await page.getByLabel('Update for this session').fill('STO wiring has not yet been checked.')
 await page.route('**/troubleshooting/follow-up',r=>r.fulfill({status:503,json:{detail:'unavailable'}}))
 await page.getByRole('button',{name:'Submit update & check documentation'}).click()
 await expect(page.getByRole('alert')).toBeVisible()
 await expect(page.getByLabel('Update for this session')).toHaveValue('STO wiring has not yet been checked.')
 await expect(page.getByRole('button',{name:'Submit update & check documentation'})).toBeEnabled()
 await expect(page.locator('.working')).toHaveCount(0)
})


test('saved nameplate is reused for detection after manual Save',async({page})=>{
 const mock=await mockApi(page);await page.goto('/')
 await page.getByRole('button',{name:'Start new troubleshooting session'}).click();await nameSession(page)
 await expect(page.getByLabel('Add equipment photos',{exact:true})).toBeEnabled()
 await page.getByLabel('Add equipment photos',{exact:true}).setInputFiles({name:'plate.jpg',mimeType:'image/jpeg',buffer:fs.readFileSync('public/replay-photo-01.jpg')})
 await page.getByLabel('View for plate.jpg').selectOption('nameplate')
 await page.getByRole('button',{name:'Save',exact:true}).click()
 await expect(page.locator('.pending-photo')).toHaveCount(0)
 await page.getByLabel('What problem are you seeing?').fill('unknown')
 await page.getByRole('button',{name:'Detect equipment / read nameplate'}).click()
 await expect(page.getByRole('button',{name:'Confirm equipment',exact:true})).toBeVisible()
 const identify=mock.calls.find(c=>c.path.endsWith('/equipment/identify'))!
 expect(identify.body).toContain('saved_image_ids');expect(identify.body).toContain('photo-0');expect(identify.body).not.toContain('unknown')
 expect(mock.calls.filter(c=>c.path.endsWith('/images')&&c.method==='POST')).toHaveLength(1)
})

test('changed follow-up guidance and confidence render with visible feedback',async({page})=>{
 const mock=await mockApi(page);await page.goto('/');await confirm(page)
 await page.getByLabel('What problem are you seeing?').fill('5091');await page.getByRole('button',{name:'Run troubleshooting'}).click()
 await page.getByLabel('Update for this session').fill('STO wiring has not yet been checked.')
 await page.route('**/troubleshooting/follow-up',r=>{
  mock.trace.follow_up_answers.push('STO wiring has not yet been checked.');mock.trace.revision++
  mock.trace.result={...mock.trace.result,confidence:'LOW',next_question:'What is the exact fault display?'}
  return r.fulfill({json:mock.trace})
 })
 await page.getByRole('button',{name:'Submit update & check documentation'}).click()
 await expect(page.getByText('Update saved. Troubleshooting guidance refreshed; review the result and next checks above.',{exact:true})).toBeVisible()
 await expect(page.locator('.result-title .badge')).toHaveText('LOW')
 await expect(page.locator('.next-question')).toContainText('What is the exact fault display?')
 await expect(page.locator('.history')).toContainText('STO wiring has not yet been checked.')
})


for(const [mode,level,label] of [['identity-exact','HIGH','ABB ACS880-01-07A2-3'],['identity-family','MEDIUM','Likely ABB ACS880 family'],['identity-low','LOW','Likely ABB ACS880 family']])test(`${mode} renders evidence granularity and confirmation guidance without model text`,async({page})=>{
 await mockApi(page,mode);await page.goto('/')
 await page.getByRole('button',{name:'Start new troubleshooting session'}).click();await nameSession(page)
 await expect(page.getByLabel('Add equipment photos',{exact:true})).toBeEnabled()
 await page.getByLabel('Add equipment photos',{exact:true}).setInputFiles({name:'front.jpg',mimeType:'image/jpeg',buffer:fs.readFileSync('public/replay-photo-01.jpg')})
 await expect(page.locator('.pending-photo')).toHaveCount(1)
 await page.getByRole('button',{name:'Detect equipment / read nameplate'}).click()
 const card=page.locator('.equipment-result')
 await expect(card.getByRole('heading',{name:label,exact:true})).toBeVisible()
 await expect(card.getByText(`Confidence: ${level}`,{exact:false})).toBeVisible()
 await expect(card.getByRole('heading',{name:'Why',exact:true})).toBeVisible()
 await expect(card.getByRole('heading',{name:'To confirm',exact:true})).toBeVisible()
 await expect(card.getByRole('button',{name:'Correct equipment',exact:true})).toHaveClass('text-button')
 if(mode!=='identity-exact')await expect(page.getByRole('button',{name:'Confirm equipment',exact:true})).toHaveCount(0)
})

test('saved front-view identification selection survives reopening without re-upload',async({page})=>{
 const mock=await mockApi(page);await page.goto('/')
 await page.getByRole('button',{name:'Start new troubleshooting session'}).click();await nameSession(page)
 await expect(page.getByLabel('Add equipment photos',{exact:true})).toBeEnabled()
 await page.getByLabel('Add equipment photos',{exact:true}).setInputFiles({name:'front.jpg',mimeType:'image/jpeg',buffer:fs.readFileSync('public/replay-photo-01.jpg')})
 await expect(page.locator('.pending-photo')).toHaveCount(1)
 await page.getByRole('button',{name:'Save',exact:true}).click()
 await expect(page.getByLabel('Use saved photo for identification')).toBeChecked()
 await page.reload();await expect(page.getByLabel('Use saved photo for identification')).toBeChecked()
 await page.getByRole('button',{name:'Detect equipment / read nameplate'}).click()
 expect(mock.calls.find(c=>c.path.endsWith('/equipment/identify'))!.body).toContain('photo-0')
 await page.getByLabel('Use saved photo for identification').click()
 await expect(page.getByLabel('Use saved photo for identification')).not.toBeChecked()
 await page.reload();await expect(page.getByLabel('Use saved photo for identification')).not.toBeChecked()
 expect(mock.calls.filter(c=>c.method==='POST'&&c.path.endsWith('/images'))).toHaveLength(1)
})


for(const shape of ['empty identification','legacy missing fields','no troubleshooting','no history','no images'])test(`reopen ${shape} without a white screen`,async({page})=>{
 await mockApi(page)
 await page.route('**/equipment',r=>r.fulfill({json:{...replay.acs880.equipment,session_id:sid,identification:{}}}))
 if(shape==='legacy missing fields'){
  await page.route('**/draft',r=>r.request().method()==='GET'?r.fulfill({json:{symptom:'Saved legacy problem'}}):r.fallback())
  await page.route('**/troubleshooting',r=>r.fulfill({json:{session_id:sid,reported_symptoms:['5091'],retrieved_evidence_history:[{run_id:rid}]}}))
 }
 if(shape==='no troubleshooting')await page.route('**/troubleshooting',r=>r.fulfill({json:null}))
 if(shape==='no history')await page.route('**/troubleshooting',r=>r.fulfill({json:{session_id:sid,result:{status:'not_run'}}}))
 if(shape==='no images')await page.route('**/visual-findings',r=>r.fulfill({json:{}}))
 const crashes:string[]=[];page.on('pageerror',e=>crashes.push(e.message))
 await page.goto('/');await page.getByRole('button',{name:'My Sessions',exact:true}).click()
 await page.getByRole('button',{name:'Continue troubleshooting'}).click()
 await expect(page.getByRole('heading',{name:'Case',exact:true})).toBeVisible()
 await expect(page.getByLabel('What problem are you seeing?')).toBeEnabled()
 await page.getByLabel('What problem are you seeing?').fill('Session still usable')
 await page.getByRole('button',{name:'Save',exact:true}).click()
 await expect(page.getByText('Saved successfully',{exact:true})).toBeVisible()
 expect(crashes).toEqual([])
})

test('nonempty malformed identification is a recoverable data error',async({page})=>{
 await mockApi(page)
 await page.route('**/equipment',r=>r.fulfill({json:{...replay.acs880.equipment,identification:{label:'Incomplete'}}}))
 await page.goto('/');await page.getByRole('button',{name:'My Sessions',exact:true}).click()
 await page.getByRole('button',{name:'Continue troubleshooting'}).click()
 await expect(page.getByRole('alert')).toContainText('identification.specificity')
 await expect(page.getByRole('button',{name:'Log out',exact:true})).toBeVisible()
 await expect(page.getByRole('button',{name:'My Sessions',exact:true})).toBeEnabled()
})


test('workspace error boundary retries or returns to My Sessions without signing out',async({page})=>{
 await mockApi(page,'identity-family');await page.goto('/')
 await page.getByRole('button',{name:'Start new troubleshooting session'}).click();await nameSession(page)
 await page.getByRole('button',{name:'My Sessions',exact:true}).click()
 await page.getByRole('button',{name:'Continue troubleshooting'}).click()
 await page.getByLabel('Model text, if known').fill('ACS880')
 // Simulate an unexpected render exception beyond the JSON validation boundary.
 await page.evaluate(()=>{
  const original=String.prototype.replaceAll
  ;(window as any).restoreFormatting=()=>{String.prototype.replaceAll=original}
  String.prototype.replaceAll=function(...args:Parameters<typeof original>){if(String(this)==='model_family')throw new Error('Injected render regression');return original.apply(this,args)}
 })
 await page.getByRole('button',{name:'Detect equipment / read nameplate'}).click()
 await expect(page.getByRole('heading',{name:'We couldn’t reopen this troubleshooting session.'})).toBeVisible()
 await page.evaluate(()=>{(window as any).restoreFormatting()})
 await page.getByRole('button',{name:'Retry',exact:true}).click()
 await expect(page.getByRole('heading',{name:'ACS880 Fault 5091',exact:true})).toBeVisible()
 await expect(page.getByRole('button',{name:'Log out',exact:true})).toBeVisible()
 await page.evaluate(()=>{
  const original=String.prototype.replaceAll
  ;(window as any).restoreFormatting=()=>{String.prototype.replaceAll=original}
  String.prototype.replaceAll=function(...args:Parameters<typeof original>){if(String(this)==='model_family')throw new Error('Injected render regression');return original.apply(this,args)}
 })
 await page.getByLabel('What problem are you seeing?').fill('Trigger render')
 await expect(page.getByRole('heading',{name:'We couldn’t reopen this troubleshooting session.'})).toBeVisible()
 await page.evaluate(()=>{(window as any).restoreFormatting()})
 await page.getByRole('button',{name:'Back to My Sessions',exact:true}).click()
 await expect(page.getByRole('heading',{name:'My Sessions',exact:true})).toBeVisible()
 await expect(page.getByRole('button',{name:'Log out',exact:true})).toBeVisible()
})


test('exact fresh backend creation shape renders without the error boundary or provider calls',async({page})=>{
 const mock=await mockApi(page)
 const crashes:string[]=[];page.on('pageerror',e=>crashes.push(e.message))
 await page.route('**/api/sessions',async r=>{
  if(r.request().method()!=='POST')return r.fallback()
  // Explicit backend serialize + metadata shape, including the formerly overwritten object.
  return r.fulfill({json:{id:sid,session_id:sid,session_name:'Fresh regression case',
   entered_equipment_text:null,raw_ocr_text:'',parsed_ocr_fields:{},ocr_results:[],input_identifiers:[],
   ranked_candidates:[],selected_candidate:null,confirmed_equipment_id:null,confirmation_status:'UNCONFIRMED',
   identification_revision:0,confidence:null,mismatch_warnings:[],confirmation_prompt:'Provide a clear nameplate.',
   confirmed_equipment_family:null,confirmed_model:null,retrieval_filters:null,identification:{},
   visual_support:'Appearance provides provisional family evidence, never an exact type code.',
   catalog_label:'Prototype equipment catalog for demo/testing.',created_at:'2026-09-25T00:00:00Z',
   updated_at:'2026-09-25T00:00:00Z',symptom_summary:'',result_status:'not_run'}})
 })
 await page.goto('/');await page.getByRole('button',{name:'Start new troubleshooting session'}).click();await nameSession(page,'Fresh regression case')
 await expect(page.getByRole('heading',{name:'Fresh regression case',exact:true})).toBeVisible()
 await expect(page.getByLabel('Model text, if known')).toBeEnabled()
 await expect(page.getByLabel('What problem are you seeing?')).toHaveValue('')
 await expect(page.getByRole('heading',{name:/We couldn’t/})).toHaveCount(0)
 expect(crashes).toEqual([])
 expect(mock.calls.some(c=>/identify|analyze|troubleshooting\/run/.test(c.path))).toBe(false)
})
