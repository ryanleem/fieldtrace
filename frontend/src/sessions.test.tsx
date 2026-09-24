import {beforeEach,afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import App from './App'
const mocks=vi.hoisted(()=>({request:vi.fn()}))
vi.mock('./api',()=>({request:mocks.request,json:(body:unknown)=>({method:'POST',body:JSON.stringify(body)}),safeLink:()=>undefined}))
vi.mock('./PrivatePhoto',()=>({default:()=>null}))
const eq={session_id:'case-a',confirmed_equipment_id:null,confirmed_model:null,confirmation_status:'UNCONFIRMED',ranked_candidates:[],mismatch_warnings:[],raw_ocr_text:'',entered_equipment_text:'ACS880-01'}
const meta={id:'case-a',session_id:'case-a',session_name:'Saved case',created_at:'2026-01-01',updated_at:'2026-01-02',confirmed_model:null,symptom_summary:'5091',result_status:'not_run'}
const trace={reported_symptoms:['5091'],follow_up_answers:['Fan runs'],checks_completed:[],measurements:[],retrieved_evidence_history:[]}
beforeEach(()=>{
 vi.clearAllMocks();sessionStorage.clear()
 HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','')};HTMLDialogElement.prototype.close=function(){this.removeAttribute('open')}
 mocks.request.mockImplementation(async(path:string,options?:RequestInit)=>{
  if(path==='/sessions')return {...eq,...meta}
  if(path.startsWith('/sessions?'))return [meta]
  if(path.endsWith('/equipment')||path.endsWith('/identify'))return eq
  if(path.endsWith('/visual-findings'))return {uploaded_images:[],aggregated_visual_findings:[],normalized_visual_findings:[]}
  if(path.endsWith('/troubleshooting'))return trace
  if(path==='/sessions/case-a')return options?.method==='PATCH'?{...meta,...JSON.parse(options.body as string)}:meta
  throw Error(path)
 })
})
afterEach(cleanup)
async function name(value='New case'){
 const dialog=await screen.findByRole('dialog',{name:'Name your troubleshooting session'})
 fireEvent.change(within(dialog).getByLabelText('Session name'),{target:{value}})
 fireEvent.click(within(dialog).getByRole('button',{name:'Start session'}))
 await waitFor(()=>expect(screen.queryByRole('dialog',{name:'Name your troubleshooting session'})).toBeNull())
}
it('does not create a new session before name confirmation; cancel preserves drafts',async()=>{
 render(<App userId="a"/>);fireEvent.change(screen.getByLabelText('Model text, if known'),{target:{value:'ACS880'}})
 fireEvent.click(screen.getByRole('button',{name:/Start new troubleshooting session/}))
 await screen.findByRole('dialog',{name:'Name your troubleshooting session'});expect(mocks.request).not.toHaveBeenCalled()
 fireEvent.click(screen.getByRole('button',{name:'Cancel'}));expect((screen.getByLabelText('Model text, if known') as HTMLInputElement).value).toBe('ACS880')
})
it('lazy naming preserves model and symptom and creates one session under repeated clicks',async()=>{
 render(<App userId="a"/>);fireEvent.change(screen.getByLabelText('Model text, if known'),{target:{value:'ACS880'}})
 fireEvent.change(screen.getByLabelText('What problem are you seeing?'),{target:{value:'5091'}})
 const detect=screen.getByRole('button',{name:'Detect equipment / read nameplate'});fireEvent.click(detect);fireEvent.click(detect)
 await name('  My case  ');await waitFor(()=>expect(mocks.request.mock.calls.some(([p])=>p.endsWith('/identify'))).toBe(true))
 expect(mocks.request.mock.calls.filter(([p])=>p==='/sessions')).toHaveLength(1)
 expect(JSON.parse(mocks.request.mock.calls.find(([p])=>p==='/sessions')![1].body).session_name).toBe('My case')
 expect((screen.getByLabelText('What problem are you seeing?') as HTMLInputElement).value).toBe('5091')
 expect((screen.getByLabelText('Model text, if known') as HTMLInputElement).value).toBe('ACS880')
})
it('My Sessions reopens saved history without POST or analysis and permits renaming',async()=>{
 render(<App userId="a"/>);fireEvent.click(screen.getByRole('button',{name:'My Sessions'}));await screen.findByText('Saved case')
 fireEvent.click(screen.getByRole('button',{name:'Rename'}));const dialog=await screen.findByRole('dialog',{name:'Rename session'})
 fireEvent.change(within(dialog).getByLabelText('Session name'),{target:{value:'Renamed'}});fireEvent.click(within(dialog).getByRole('button',{name:'Save name'}))
 await waitFor(()=>expect(mocks.request.mock.calls.some(([,o])=>o?.method==='PATCH')).toBe(true))
 await waitFor(()=>expect((screen.getByRole('button',{name:'Continue troubleshooting'}) as HTMLButtonElement).disabled).toBe(false))
 fireEvent.click(screen.getByRole('button',{name:'Continue troubleshooting'}));await screen.findByText('Follow-up saved: Fan runs')
 expect(mocks.request.mock.calls.filter(([,o])=>o?.method==='POST')).toHaveLength(0)
 expect(sessionStorage.getItem('fieldtrace.session.a')).toBe('case-a')
})
it('failed session creation preserves typed input',async()=>{
 mocks.request.mockRejectedValue(new Error('Unavailable'));render(<App userId="a"/> )
 fireEvent.change(screen.getByLabelText('Model text, if known'),{target:{value:'ACS880'}})
 fireEvent.click(screen.getByRole('button',{name:'Detect equipment / read nameplate'}));await name()
 await screen.findByRole('alert');expect((screen.getByLabelText('Model text, if known') as HTMLInputElement).value).toBe('ACS880')
 expect(sessionStorage.getItem('fieldtrace.session.a')).toBeNull()
})
