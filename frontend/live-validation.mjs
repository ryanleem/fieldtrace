// Opt-in local validation: real backend and paid configured providers, no API mocks.
import {chromium} from '@playwright/test'
import fs from 'node:fs'
const out=process.env.UI_EVALUATION_DIR||'../data/evaluation/ui';fs.mkdirSync(out,{recursive:true})
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true})
const page=await browser.newPage({viewport:{width:1440,height:1050}})
page.setDefaultTimeout(180000)
const report={mode:'LIVE backend and configured providers',requests:[],scenarios:[]}
page.on('request',r=>{if(r.url().includes('/api/'))report.requests.push({method:r.method(),path:new URL(r.url()).pathname})})
async function idle(){await page.locator('.working').waitFor({state:'hidden',timeout:900000})}
async function state(){return page.evaluate(async()=>{const id=sessionStorage.getItem('fieldtrace.session');return {session_id:id,trace:await fetch(`/api/sessions/${id}/troubleshooting`).then(r=>r.json()),visual:await fetch(`/api/sessions/${id}/visual-findings`).then(r=>r.json())}})}
async function confirm(){await page.getByRole('button',{name:'Start new troubleshooting session'}).click();await idle();await page.getByLabel('Model text, if known').fill('ABB ACS880-01');await page.getByRole('button',{name:'Detect equipment / read nameplate'}).click();await idle();await page.getByRole('button',{name:'Confirm equipment',exact:true}).click();await idle()}
try{
 await page.goto(process.env.UI_BASE_URL||'http://127.0.0.1:5173');await confirm()
 await page.screenshot({path:`${out}/live-intake.png`,fullPage:true})
 await page.getByLabel('What problem are you seeing?').fill('Drive shows fault 5091')
 await page.getByRole('button',{name:'Run troubleshooting',exact:false}).click();await idle()
 report.scenarios.push({name:'ACS880 fault 5091',...await state()});console.log('ACS880 result',report.scenarios.at(-1).trace.result.status,report.scenarios.at(-1).trace.result.confidence)
 await page.screenshot({path:`${out}/live-acs880.png`,fullPage:true})
 if(await page.locator('.source-row').count()){
  await page.locator('.source-row').first().click();await page.locator('.excerpt').waitFor();report.source_excerpt=await page.locator('.excerpt').innerText();report.source_link=await page.getByRole('link',{name:'Open manual page'}).getAttribute('href');await page.screenshot({path:`${out}/live-source.png`});await page.keyboard.press('Escape')
 }
 const upstream=()=>report.requests.filter(r=>/identify|confirm|analyze/.test(r.path)).length
 const before=upstream()
 await page.getByLabel('Update for this session').fill('STO wiring has not yet been checked.')
 await page.getByRole('button',{name:'Submit update & check documentation'}).click();await idle()
 report.scenarios.push({name:'Same-session follow-up',upstream_calls_before:before,upstream_calls_after:upstream(),...await state()});console.log('Follow-up result',report.scenarios.at(-1).trace.result.status)
 await page.getByLabel('Add equipment photos',{exact:true}).setInputFiles('public/replay-photo-01.jpg')
 await page.getByLabel('View for replay-photo-01.jpg').selectOption('close_up')
 await page.getByLabel('Photo note').fill('Generic corroded connector reference photo for UI validation only; this is not an ABB equipment identification test.')
 await page.getByRole('button',{name:'Save photos & inspect visible conditions'}).click();await idle()
 report.scenarios.push({name:'Generic real-photo visible inspection in controlled session',...await state()});console.log('Photo status',report.scenarios.at(-1).visual.uploaded_images.map(p=>p.analysis_status))
 await page.screenshot({path:`${out}/live-photo.png`,fullPage:true})
 // Controlled UI integration fixture: generic photo is explicitly labeled, not claimed
 // to depict the confirmed drive. Verify context transfer, not diagnostic accuracy.
 await page.getByRole('button',{name:'Run troubleshooting',exact:false}).click();await idle()
 const visualRun=await state();report.scenarios.push({name:'Visual context integration (generic reference fixture)',...visualRun})
 report.visual_query=await page.evaluate(async()=>{
  const id=sessionStorage.getItem('fieldtrace.session'),t=await fetch(`/api/sessions/${id}/troubleshooting`).then(r=>r.json())
  const rid=t.retrieved_evidence_history.at(-1).run_id
  const run=await fetch(`/api/sessions/${id}/troubleshooting/runs/${rid}?include_evidence=true`).then(r=>r.json())
  return run.audit?.attempts?.map(a=>a.query)
 })
 await confirm();await page.getByLabel('What problem are you seeing?').fill('Something seems wrong, but I have no fault code, measurements or specific observation.')
 await page.getByRole('button',{name:'Run troubleshooting',exact:false}).click();await idle()
 report.scenarios.push({name:'Weak evidence',...await state()});console.log('Weak result',report.scenarios.at(-1).trace.result.status,report.scenarios.at(-1).trace.result.confidence)
 await page.screenshot({path:`${out}/live-weak.png`,fullPage:true})
 const previous=report.scenarios.at(-1).session_id
 await page.getByRole('button',{name:'Start new troubleshooting session'}).click();await idle()
 report.reset={previous_session:previous,...await state(),symptom:await page.getByLabel('What problem are you seeing?').inputValue()}
 await page.screenshot({path:`${out}/live-reset.png`,fullPage:true})
}catch(e){report.error=String(e);console.error(String(e));process.exitCode=1}
finally{fs.writeFileSync(`${out}/live-workspace.json`,JSON.stringify(report,null,2));await browser.close()}
