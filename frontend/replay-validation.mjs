// Requires explicit replay server on 5174. No API routes are mocked or called.
import {chromium,expect} from '@playwright/test'
import fs from 'node:fs'
const out='../data/evaluation/ui/step6';fs.mkdirSync(out,{recursive:true})
const saved=JSON.parse(fs.readFileSync('public/demo.json','utf8'))
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe'})
const context=await browser.newContext({viewport:{width:1440,height:1050},recordVideo:{dir:out,size:{width:1440,height:1050}}})
const page=await context.newPage(),requests=[],external=[]
page.on('request',r=>{const u=new URL(r.url());if(u.pathname.startsWith('/api/'))requests.push(u.pathname);if(u.hostname!=='127.0.0.1')external.push(u.origin)})
const report={mode:'explicit recorded replay',api_requests:requests,external_requests:external}
try{
 await page.goto('http://127.0.0.1:5174')
 await expect(page.getByText('DEMO REPLAY · Not a fresh analysis',{exact:true})).toBeVisible()
 await page.getByRole('button',{name:'ACS880 fault 5091',exact:true}).click()
 await expect(page.locator('.cause-title')).toHaveText(saved.acs880.trace.result.primary_cause.label)
 await expect(page.locator('.result-title .badge')).toHaveText('MEDIUM')
 await page.locator('.result-panel').scrollIntoViewIfNeeded();await page.waitForTimeout(2500)
 await page.screenshot({path:`${out}/replay-primary.png`,fullPage:true})
 await page.locator('.source-row').first().click()
 await expect(page.locator('.excerpt')).toContainText('5091')
 await page.waitForTimeout(2500);await page.screenshot({path:`${out}/replay-source.png`});await page.keyboard.press('Escape')
 await page.getByRole('button',{name:'Motor uncertainty fixture'}).click()
 await expect(page.locator('.replay-banner')).toContainText('Temporary motor-family fixture for reasoning validation only.')
 await expect(page.locator('.result-title .badge')).toHaveText('LOW')
 await expect(page.locator('.cause-title')).toHaveCount(0)
 await expect(page.locator('.next-question')).toContainText(saved.motor.trace.result.next_question)
 await page.locator('.result-panel').scrollIntoViewIfNeeded();await page.waitForTimeout(2500)
 await page.screenshot({path:`${out}/replay-motor-low.png`,fullPage:true})
 await page.getByRole('button',{name:'Recorded visible finding'}).click()
 await expect(page.locator('.finding').first()).toBeVisible()
 await page.locator('.finding').first().scrollIntoViewIfNeeded();await page.waitForTimeout(2500)
 await page.screenshot({path:`${out}/replay-visual.png`,fullPage:true})
 await page.getByRole('button',{name:'Reset demo'}).click()
 await expect(page.locator('.finding')).toHaveCount(0);await expect(page.locator('.cause-title')).toHaveCount(0)
 await expect(page.getByLabel('What problem are you seeing?')).toHaveValue('')
 await page.getByRole('button',{name:'ACS880 fault 5091',exact:true}).click()
 await expect(page.locator('.cause-title')).toBeVisible()
 expect(requests).toHaveLength(0);expect(external).toHaveLength(0)
 report.passed=true
}catch(e){report.error=String(e);process.exitCode=1}
finally{await context.close();await page.video().saveAs(`${out}/recorded-replay-backup.webm`);await browser.close();fs.writeFileSync(`${out}/replay-validation.json`,JSON.stringify(report,null,2));console.log(JSON.stringify(report))}
