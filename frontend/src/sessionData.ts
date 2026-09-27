// Runtime boundary for persisted session data. TypeScript casts do not validate JSON.
export class SessionDataError extends Error {
 constructor(field:string){super(`Saved session data is invalid (${field}). Refresh or open another session.`)}
}
type Row=Record<string,any>
function object(value:unknown,field:string):Row {
 if(value==null)return {}
 if(typeof value!=='object'||Array.isArray(value))throw new SessionDataError(field)
 return value as Row
}
function string(value:unknown,field:string,fallback=''):string {
 if(value==null)return fallback
 if(typeof value!=='string')throw new SessionDataError(field)
 return value
}
function required(value:unknown,field:string):string {const text=string(value,field);if(!text.trim())throw new SessionDataError(field);return text}
function list(value:unknown,field:string):any[]{if(value==null)return [];if(!Array.isArray(value))throw new SessionDataError(field);return value}
function strings(value:unknown,field:string){return list(value,field).map(v=>string(v,field))}
function level(value:unknown,fallback='LOW'){const text=string(value,'confidence',fallback);if(!['HIGH','MEDIUM','LOW'].includes(text))throw new SessionDataError('confidence');return text}
export function normalizeDraft(value:unknown){
 const r=object(value,'draft'),m=object(r.measurement,'measurement')
 const entry=string(r.entry_type,'entry_type','answer')
 if(!['answer','check','measurement'].includes(entry))throw new SessionDataError('entry_type')
 // Legacy draft choices share the new text-entry UI; persisted history stays intact.
 return {...r,model:string(r.model,'model'),symptom:string(r.symptom,'symptom'),followup:string(r.followup,'followup'),entry_type:entry==='measurement'?'measurement':'answer',
 measurement:{name:string(m.name,'measurement.name','temperature'),value:string(m.value,'measurement.value'),unit:string(m.unit,'measurement.unit','C'),location:string(m.location,'measurement.location')}}
}
export function normalizeEquipment(value:unknown){
 const r=object(value,'equipment'),identity=object(r.identification,'identification')
 let identification: null | {specificity:string;label:string;confidence:string;why:string;to_confirm:string;provider_error:string}=null
 if(Object.keys(identity).length){
  const specificity=required(identity.specificity,'identification.specificity')
  if(!['exact_type','supported_model','model_family','manufacturer','insufficient'].includes(specificity))throw new SessionDataError('identification.specificity')
  identification={...identity,specificity,label:required(identity.label,'identification.label'),confidence:level(identity.confidence),why:string(identity.why,'identification.why'),to_confirm:string(identity.to_confirm,'identification.to_confirm'),provider_error:string(identity.provider_error,'identification.provider_error')}
 }
 const status=string(r.confirmation_status,'confirmation_status','UNCONFIRMED')
 if(status==='CONFIRMED'&&(!r.confirmed_equipment_id||!r.confirmed_model))throw new SessionDataError('confirmed equipment')
 return {...r,confirmed_model:r.confirmed_model==null?null:string(r.confirmed_model,'confirmed_model'),confirmed_equipment_family:r.confirmed_equipment_family==null?null:string(r.confirmed_equipment_family,'confirmed_equipment_family'),confirmed_equipment_id:r.confirmed_equipment_id==null?null:required(r.confirmed_equipment_id,'confirmed_equipment_id'),session_id:required(r.session_id,'equipment.session_id'),identification,confirmation_status:status,raw_ocr_text:string(r.raw_ocr_text,'raw_ocr_text'),confidence:r.confidence==null?null:level(r.confidence),
 mismatch_warnings:strings(r.mismatch_warnings,'mismatch_warnings'),ranked_candidates:list(r.ranked_candidates,'ranked_candidates').map(item=>{
 const c=object(item,'candidate');return {...c,candidate_id:required(c.candidate_id,'candidate_id'),candidate_model:required(c.candidate_model,'candidate_model'),match_level:level(c.match_level)}
 })}
}
function photo(value:unknown){const r=object(value,'photo');return {...r,id:required(r.id,'photo.id'),original_filename:string(r.original_filename,'filename','Saved photo'),view_label:string(r.view_label,'view_label','additional'),analysis_status:string(r.analysis_status,'analysis_status','pending')}}
function finding(value:unknown){const r=object(value,'finding');return {...r,id:required(r.id,'finding.id'),issue_type:required(r.issue_type,'finding.issue_type'),description:required(r.description,'finding.description'),visual_confidence:string(r.visual_confidence,'visual_confidence','unknown'),supporting_image_ids:strings(r.supporting_image_ids??(r.image_id?[r.image_id]:[]),'supporting_image_ids')}}
export function normalizeVisual(value:unknown){const r=object(value,'visual');return {...r,uploaded_images:list(r.uploaded_images,'uploaded_images').map(photo),aggregated_visual_findings:list(r.aggregated_visual_findings,'aggregated_visual_findings').map(finding),normalized_visual_findings:list(r.normalized_visual_findings,'normalized_visual_findings').map(finding)}}
function citation(value:unknown){const r=object(value,'citation');if(!Number.isInteger(r.page_number)||r.page_number<1)throw new SessionDataError('citation.page_number');return {...r,chunk_id:required(r.chunk_id,'citation.chunk_id'),document_title:required(r.document_title,'citation.document_title')}}
function cause(value:unknown){const r=object(value,'cause');return {...r,label:required(r.label,'cause.label'),rationale:string(r.rationale,'cause.rationale'),citation_chunk_ids:strings(r.citation_chunk_ids,'cause.citations')}}
export function normalizeTrace(value:unknown){
 const r=object(value,'troubleshooting'),result=object(r.result,'result')
 const status=string(result.status,'result.status','not_run')
 if(status==='suspected_cause'&&!result.primary_cause)throw new SessionDataError('primary_cause')
 return {...r,reported_symptoms:strings(r.reported_symptoms,'reported_symptoms'),follow_up_answers:strings(r.follow_up_answers,'follow_up_answers'),checks_completed:strings(r.checks_completed,'checks_completed'),
 measurements:list(r.measurements,'measurements').map(v=>{const m=object(v,'measurement');return {...m,name:string(m.name,'measurement.name'),value:string(m.value,'measurement.value'),unit:string(m.unit,'measurement.unit'),location:string(m.location,'measurement.location')}}),
 retrieved_evidence_history:list(r.retrieved_evidence_history,'history').map(v=>{const h=object(v,'history');return {...h,run_id:required(h.run_id,'history.run_id'),status:string(h.status,'history.status','status_unavailable'),created_at:string(h.created_at,'history.created_at'),sources:list(h.sources,'history.sources').map(citation)}}),
 result:{...result,status,message:string(result.message,'result.message'),confidence:level(result.confidence),primary_cause:result.primary_cause==null?null:cause(result.primary_cause),alternative_causes:list(result.alternative_causes,'alternatives').map(cause),
 recommended_actions:list(result.recommended_actions,'actions').map(v=>{const a=object(v,'action');return {...a,action:required(a.action,'action.text'),citation_chunk_ids:strings(a.citation_chunk_ids,'action.citations')}}),
 technical_claims:list(result.technical_claims,'claims').map(v=>{const c=object(v,'claim');return {...c,claim_id:required(c.claim_id,'claim.id'),text:required(c.text,'claim.text'),citation_chunk_ids:strings(c.citation_chunk_ids,'claim.citations')}}),
 next_question:string(result.next_question,'next_question'),question_sources:strings(result.question_sources,'question_sources'),missing_information:strings(result.missing_information,'missing_information'),sources:list(result.sources,'sources').map(citation),conflicts:list(result.conflicts,'conflicts').map(v=>{const c=object(v,'conflict');return {...c,relationship:required(c.relationship,'relationship'),citation_chunk_ids:strings(c.citation_chunk_ids,'conflict.citations')}})}}
}
function metadata(value:unknown){
 const r=object(value,'session')
 // Whitelist metadata: spreading the original mixed creation payload here would
 // overwrite normalized equipment fields (notably identification: {}).
 return {id:required(r.id??r.session_id,'session.id'),session_id:required(r.session_id??r.id,'session.id'),session_name:required(r.session_name,'session_name'),
 created_at:string(r.created_at,'created_at'),updated_at:string(r.updated_at,'updated_at'),confirmed_model:r.confirmed_model==null?null:string(r.confirmed_model,'confirmed_model'),
 symptom_summary:string(r.symptom_summary,'symptom_summary'),confidence:r.confidence==null?null:level(r.confidence),result_status:string(r.result_status,'result_status','not_run')}
}
export function normalizeSessionResponse(path:string,value:unknown):unknown {
 const route=path.split('?')[0]
 if(route==='/sessions')return Array.isArray(value)?value.map(metadata):{...normalizeEquipment(value),...metadata(value)}
 if(/^\/sessions\/[^/]+$/.test(route))return object(value,'session').deleted?value:metadata(value)
 if(route.endsWith('/draft'))return normalizeDraft(value)
 if(/\/equipment(?:\/[^/]+)?$/.test(route))return normalizeEquipment(value)
 if(route.endsWith('/visual-findings'))return normalizeVisual(value)
 if(route.endsWith('/images'))return list(value,'images').map(photo)
 if(route.endsWith('/identification'))return photo(value)
 if(/\/troubleshooting(?:\/(?:symptoms|run|follow-up))?$/.test(route))return normalizeTrace(value)
 return value
}
