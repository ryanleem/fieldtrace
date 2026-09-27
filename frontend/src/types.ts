export type Confidence = 'HIGH' | 'MEDIUM' | 'LOW'
export type Candidate = {candidate_id:string;candidate_model:string;confirmable?:boolean;equipment_family?:string;candidate_family?:string;match_level:Confidence}
export type Identification={specificity:string;label:string;confidence:Confidence;why:string;to_confirm:string;exact_type_confirmed:boolean;provider_error?:string}
export type Equipment = {identification?:Identification|null;session_id:string;entered_equipment_text?:string|null;confirmed_equipment_id:string|null;confirmed_model:string|null;confirmed_equipment_family:string|null;confirmation_status:string;identification_revision:number;ranked_candidates:Candidate[];mismatch_warnings:string[];confidence:Confidence|null;raw_ocr_text:string}
export type Photo = {id:string;use_for_identification?:boolean|null;content_sha256?:string|null;equipment_id:string|null;original_filename:string;view_label:string;user_note:string|null;analysis_status:string;analysis_error?:string|null}
export type Finding = {id:string;equipment_id?:string|null;image_id?:string;supporting_image_ids?:string[];issue_type:string;description:string;location:string;visual_confidence:string;severity:string}
export type Visual = {uploaded_images:Photo[];aggregated_visual_findings:Finding[];normalized_visual_findings:Finding[]}
export type Citation = {chunk_id:string;document_title:string;page_number:number;section_title:string|null;citation_url:string|null;source_url:string|null;document_number?:string;revision?:string;chunk_text?:string}
export type Cause = {label:string;rationale:string;citation_chunk_ids:string[]}
export type Result = {status:string;message:string;primary_cause:Cause|null;alternative_causes:Cause[];confidence:Confidence;recommended_actions:{action:string;citation_chunk_ids:string[]}[];technical_claims:{claim_id:string;text:string;citation_chunk_ids:string[]}[];next_question:string;question_sources?:string[];missing_information:string[];sources:Citation[];conflicts:{relationship:string;citation_chunk_ids:string[]}[]}
export type Trace = {session_id:string;revision:number;result:Result;reported_symptoms:string[];follow_up_answers:string[];checks_completed:string[];measurements:{name:string;value:string;unit:string;location:string}[];retrieved_evidence_history:{run_id:string;status:string;created_at:string;sources:Citation[]}[]}
export type Replay = {title:string;disclosure:string;equipment:Equipment;trace:Trace;visual:Visual;source_text:Record<string,Citation>;image_urls?:Record<string,string>;attribution?:string}

export type SessionMeta = {id:string;session_id:string;session_name:string;created_at:string;updated_at:string;confirmed_model:string|null;symptom_summary:string;confidence:string|null;result_status:string}
