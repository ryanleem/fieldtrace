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
  if(path.endsWith('/draft'))return options?.method==='PUT'?JSON.parse(options.body as string):{model:'ACS880-01',symptom:'5091',followup:'',entry_type:'answer',measurement:{name:'temperature',value:'',unit:'C',location:''}}
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
it('locks all session actions until explicit naming and cancel stays locked',async()=>{
 render(<App userId="a"/> )
 const model=screen.getByLabelText('Model text, if known')
 expect(model.matches(':disabled')).toBe(true)
 expect(screen.getByLabelText('What problem are you seeing?').matches(':disabled')).toBe(true)
 expect(screen.getByLabelText('Add equipment photos').matches(':disabled')).toBe(true)
 fireEvent.click(screen.getByRole('button',{name:/Start new troubleshooting session/}))
 await screen.findByRole('dialog',{name:'Name your troubleshooting session'});expect(mocks.request).not.toHaveBeenCalled()
 fireEvent.click(screen.getByRole('button',{name:'Cancel'}))
 await waitFor(()=>expect(screen.queryByRole('dialog')).toBeNull())
 expect(model.matches(':disabled')).toBe(true)
})
it('explicit naming trims input and repeated start creates exactly one session',async()=>{
 render(<App userId="a"/> )
 const start=screen.getByRole('button',{name:/Start new troubleshooting session/});fireEvent.click(start);fireEvent.click(start)
 await name('  My case  ')
 await waitFor(()=>expect(screen.getByLabelText('Model text, if known').matches(':disabled')).toBe(false))
 expect(mocks.request.mock.calls.filter(([p])=>p==='/sessions')).toHaveLength(1)
 expect(JSON.parse(mocks.request.mock.calls.find(([p])=>p==='/sessions')![1].body).session_name).toBe('My case')
 expect(screen.getByRole('heading',{name:'Saved case'})).toBeTruthy()
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
it('failed creation leaves the workspace locked',async()=>{
 mocks.request.mockRejectedValue(new Error('Unavailable'));render(<App userId="a"/> )
 fireEvent.click(screen.getByRole('button',{name:/Start new troubleshooting session/}));await name()
 await screen.findByRole('alert');expect(screen.getByLabelText('Model text, if known').matches(':disabled')).toBe(true)
 expect(sessionStorage.getItem('fieldtrace.session.a')).toBeNull()
})

it('deleting a non-active session removes its card and leaves the workspace locked',async()=>{
 render(<App userId="a"/> )
 fireEvent.click(screen.getByRole('button',{name:'My Sessions'}));await screen.findByText('Saved case')
 fireEvent.click(screen.getByRole('button',{name:'Delete'}))
 const dialog=await screen.findByRole('dialog',{name:'Delete troubleshooting session?'})
 expect(within(dialog).getByText(/permanently removed/)).toBeTruthy()
 fireEvent.click(within(dialog).getByRole('button',{name:'Delete session'}))
 await screen.findByText('Session deleted.')
 expect(screen.queryByText('Saved case')).toBeNull()
 expect(mocks.request.mock.calls.filter(([,o])=>o?.method==='DELETE')).toHaveLength(1)
 fireEvent.click(screen.getByRole('button',{name:'Workspace'}))
 expect(screen.getByLabelText('Model text, if known').matches(':disabled')).toBe(true)
})
