import {test,expect,Page} from '@playwright/test'
import fs from 'node:fs'
const replay=JSON.parse(fs.readFileSync('public/demo.json','utf8'))
const sid='10000000-0000-0000-0000-000000000001',rid='20000000-0000-0000-0000-000000000001'
async function mockApi(page:Page,mode='success'){
 const eq={...replay.acs880.equipment,session_id:sid,confirmation_status:'UNCONFIRMED',confirmed_equipment_id:null,confirmed_model:null,confidence:null,ranked_candidates:[] as any[]}
 const v={uploaded_images:[] as any[],aggregated_visual_findings:[] as any[],normalized_visual_findings:[]}
 const trace={...structuredClone(replay.acs880.trace),session_id:sid,revision:0,reported_symptoms:[],follow_up_answers:[],checks_completed:[],measurements:[],retrieved_evidence_history:[],result:{...replay.weak.trace.result,status:'not_run',next_question:''}}
 const calls:{path:string;method:string;body:string}[]=[];let failures=mode==='http-failure'?1:0
 await page.route('**/api/**',async route=>{
  const req=route.request(),path=new URL(req.url()).pathname.replace('/api',''),method=req.method(),body=req.postData()||'';calls.push({path,method,body})
  const ok=(data:any)=>route.fulfill({json:data})
  if(path.endsWith('/file'))return route.fulfill({path:'public/replay-photo-01.jpg',contentType:'image/jpeg'})
  if(path.includes('/sources/'))return ok(replay.acs880.source_text[path.split('/').at(-1)!])
  if(path==='/sessions'&&method==='POST')return ok(eq)
  if(path.endsWith('/equipment/identify')){
   eq.ranked_candidates=[{candidate_id:'abb-acs880-01',candidate_model:'ACS880-01',match_level:'HIGH',equipment_family:'ACS880'}];eq.confirmation_status='SUGGESTED';eq.identification_revision=1
   if(mode==='mismatch')eq.mismatch_warnings=['Entered equipment differs from visible nameplate text.']
   return ok(eq)
  }
  if(path.endsWith('/equipment/confirm')){expect(JSON.parse(body).equipment_id).toBe('abb-acs880-01');Object.assign(eq,{confirmation_status:'CONFIRMED',confirmed_equipment_id:'abb-acs880-01',confirmed_model:'ACS880-01',confidence:'HIGH'});return ok(eq)}
  if(path.endsWith('/equipment'))return ok(eq)
  if(path.endsWith('/images')&&method==='POST'){
   const views=JSON.parse(body.match(/name="view_labels"\r\n\r\n([^\r]+)/)?.[1]||'[]')
   const notes=JSON.parse(body.match(/name="user_notes"\r\n\r\n([^\r]+)/)?.[1]||'[]')
   const items=views.map((view:string,i:number)=>({id:`photo-${v.uploaded_images.length+i}`,equipment_id:eq.confirmed_equipment_id,original_filename:`photo-${i}.jpg`,view_label:view,user_note:notes[i],analysis_status:'pending'}))
   v.uploaded_images.push(...items);return ok(items)
  }
  if(path.endsWith('/images'))return ok(v.uploaded_images)
  if(path.endsWith('/analyze')){
   const image=v.uploaded_images.find(x=>path.includes(x.id));image.analysis_status=mode==='vision-failure'?'failed':'completed'
   if(mode!=='vision-failure')v.aggregated_visual_findings=[{id:'f1',equipment_id:eq.confirmed_equipment_id,supporting_image_ids:v.uploaded_images.map(x=>x.id),issue_type:'corrosion',location:'contacts',description:'Visible corrosion on contacts.',visual_confidence:'high',severity:'medium'}]
   return ok({image,findings:[]})
  }
  if(path.endsWith('/visual-findings'))return ok(v)
  if(path.endsWith('/symptoms')){trace.reported_symptoms.push(JSON.parse(body).symptom);trace.revision++;trace.result={...replay.weak.trace.result,status:'not_run',next_question:''};return ok(trace)}
  if(path.endsWith('/run')||path.endsWith('/follow-up')){
   if(path.endsWith('/follow-up')){const data=JSON.parse(body);trace.follow_up_answers.push(data.answer);trace.revision++}
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
 await page.getByRole('button',{name:'Start new troubleshooting session'}).click()
 await page.getByLabel('Model text, if known').fill('ABB ACS880-01')
 await page.getByRole('button',{name:'Detect equipment / read nameplate'}).click()
 await page.getByRole('button',{name:'Confirm equipment',exact:true}).click()
 await expect(page.getByText('CONFIRMED EQUIPMENT',{exact:true})).toBeVisible()
}
test('complete multi-photo, identification, result, citation and follow-up workflow',async({page})=>{
 const mock=await mockApi(page);await page.goto('/')
 await page.getByRole('button',{name:'Start new troubleshooting session'}).click()
 await page.getByLabel('Add equipment photos',{exact:true}).setInputFiles([
  {name:'front.jpg',mimeType:'image/jpeg',buffer:fs.readFileSync('public/replay-photo-01.jpg')},
  {name:'nameplate.jpg',mimeType:'image/jpeg',buffer:fs.readFileSync('public/replay-photo-01.jpg')}])
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
 expect(await page.evaluate(()=>sessionStorage.getItem('fieldtrace.session'))).toBe(sid)
 await page.getByRole('button',{name:'Refresh session status'}).click()
 await page.getByRole('button',{name:'Run troubleshooting'}).click()
 await expect(page.locator('.cause-title')).toBeVisible();expect(mock.trace.reported_symptoms).toContain('Fault 5091')
})
test('provider failure is not disguised as a low-evidence success',async({page})=>{
 await mockApi(page,'provider-failure');await page.goto('/');await confirm(page)
 await page.getByLabel('What problem are you seeing?').fill('Fault 5091');await page.getByRole('button',{name:'Run troubleshooting'}).click()
 await expect(page.getByRole('heading',{name:'Troubleshooting service unavailable'})).toBeVisible()
 await expect(page.getByRole('button',{name:'Retry troubleshooting'})).toBeVisible();await expect(page.locator('.cause-title')).toHaveCount(0)
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
 await page.getByRole('button',{name:'Start new troubleshooting session'}).click();await page.getByLabel('Model text, if known').fill('ACS580-01')
 await page.getByRole('button',{name:'Detect equipment / read nameplate'}).click()
 await expect(page.getByText('Entered equipment differs from visible nameplate text.')).toBeVisible()
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true)
 await expect(page.getByRole('button',{name:'Run troubleshooting'})).toBeDisabled()
})
