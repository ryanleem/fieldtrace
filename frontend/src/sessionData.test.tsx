import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {normalizeEquipment,normalizeDraft,normalizeTrace,normalizeVisual,normalizeSessionResponse} from './sessionData'
import {WorkspaceErrorBoundary} from './WorkspaceBoundary'
afterEach(()=>{cleanup();vi.restoreAllMocks()})
it('normalizes the exact legacy empty-identification regression without erasing confirmation',()=>{
 const eq=normalizeEquipment({session_id:'case',identification:{},confirmation_status:'CONFIRMED',confirmed_equipment_id:'abb-acs880-01',confirmed_model:'ACS880-01'})
 expect(eq.identification).toBeNull();expect(eq.confirmed_model).toBe('ACS880-01');expect(eq.ranked_candidates).toEqual([])
})
it('keeps current identification details and flags malformed nonempty identity',()=>{
 const identification={specificity:'model_family',label:'Likely ABB ACS880 family',confidence:'LOW',why:'Visible layout',to_confirm:'Nameplate needed'}
 expect(normalizeEquipment({session_id:'case',identification}).identification).toMatchObject(identification)
 expect(()=>normalizeEquipment({session_id:'case',identification:{label:'ACS880'}})).toThrow('identification.specificity')
 expect(()=>normalizeEquipment({session_id:'case',identification:{...identification,specificity:42}})).toThrow('identification.specificity')
})
it('defaults missing draft, measurement and feedback inputs to safe strings',()=>{
 const draft=normalizeDraft({symptom:'5091',measurement:{value:'42'}})
 expect(draft.symptom).toBe('5091');expect(draft.model).toBe('');expect(draft.followup).toBe('');expect(draft.entry_type).toBe('answer');expect(draft.measurement.unit).toBe('C')
 expect(()=>normalizeDraft({model:17})).toThrow('model')
})
it('handles absent troubleshooting, history and images',()=>{
 expect(normalizeTrace(null).result.status).toBe('not_run')
 expect(normalizeTrace({}).retrieved_evidence_history).toEqual([])
 expect(normalizeVisual(null).uploaded_images).toEqual([])
 expect(normalizeTrace({retrieved_evidence_history:[{run_id:'run'}]}).retrieved_evidence_history[0].status).toBe('status_unavailable')
 expect(normalizeSessionResponse('/sessions',[{id:'case',session_name:'Legacy'}])).toMatchObject([{result_status:'not_run'}])
})
it('normalizes optional explanation text but refuses missing technical identity',()=>{
 expect(normalizeTrace({result:{primary_cause:{label:'Direction',citation_chunk_ids:[]}}}).result.primary_cause?.rationale).toBe('')
 expect(()=>normalizeVisual({aggregated_visual_findings:[{id:'finding'}]})).toThrow('finding.issue_type')
 expect(()=>normalizeEquipment({session_id:'case',confirmation_status:'CONFIRMED'})).toThrow('confirmed equipment')
})
it('error boundary offers both recovery actions instead of a blank workspace',()=>{
 vi.spyOn(console,'error').mockImplementation(()=>{})
 const retry=vi.fn(),back=vi.fn()
 function Broken():never{throw new Error('unexpected malformed render')}
 render(<WorkspaceErrorBoundary onRetry={retry} onBack={back}><Broken/></WorkspaceErrorBoundary>)
 expect(screen.getByRole('heading').textContent).toBe('We couldn’t reopen this troubleshooting session.')
 fireEvent.click(screen.getByRole('button',{name:'Retry'}));fireEvent.click(screen.getByRole('button',{name:'Back to My Sessions'}))
 expect(retry).toHaveBeenCalledOnce();expect(back).toHaveBeenCalledOnce()
})
it('boundary renders a healthy workspace normally',()=>{
 render(<WorkspaceErrorBoundary onRetry={()=>{}} onBack={()=>{}}><h1>Current session</h1></WorkspaceErrorBoundary>)
 expect(screen.getByRole('heading').textContent).toBe('Current session')
})


it('mixed POST /sessions payload cannot overwrite normalized equipment with raw metadata',()=>{
 const raw={id:'case',session_id:'case',session_name:'New case',identification:{},raw_ocr_text:null,
 ranked_candidates:null,mismatch_warnings:null,confirmed_equipment_id:null,confirmed_model:null,
 confirmation_status:'UNCONFIRMED',confidence:null,entered_equipment_text:null,result_status:'not_run'}
 const created=normalizeSessionResponse('/sessions',raw) as ReturnType<typeof normalizeEquipment>
 const reopened=normalizeSessionResponse('/sessions/case/equipment',raw) as ReturnType<typeof normalizeEquipment>
 expect(created.identification).toBeNull()
 expect(created.raw_ocr_text).toBe('');expect(created.ranked_candidates).toEqual([])
 expect(created.mismatch_warnings).toEqual([])
 expect(created.identification).toEqual(reopened.identification)
 expect(created.ranked_candidates).toEqual(reopened.ranked_candidates)
})
it('creation boundary uses creation-specific wording',()=>{
 vi.spyOn(console,'error').mockImplementation(()=>{})
 function Broken():never{throw new Error('create render')}
 render(<WorkspaceErrorBoundary operation="create" onRetry={()=>{}} onBack={()=>{}}><Broken/></WorkspaceErrorBoundary>)
 expect(screen.getByRole('heading').textContent).toBe('We couldn’t start a new troubleshooting session.')
})
