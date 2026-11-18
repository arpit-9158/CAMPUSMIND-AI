import axios from 'axios'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

export const api = axios.create({ baseURL: apiBaseUrl.replace(/\/$/, ''), timeout: 180000 })
export type RetrievedSource = {document_title:string;source_filename:string;category:string;passage:string;retrieved_content:string;source_id:string;document_id:string;retrieval_score:number;relevance_score:number;distance:number;score_type:string;metadata:Record<string,unknown>}
export type AgentEvent = {event_id:string;session_id:string;event_type:string;tool_name?:string;status:string;timestamp:string;execution_summary:string;safe_result_summary:string;duration_ms?:number}
export type ChatResult = { answer: string; tools_used: string[]; sources: RetrievedSource[]; execution_summary: (AgentEvent&{type:string;tool?:string;detail?:string;tools?:string[]})[]; tool_results: {tool:string;input:Record<string,unknown>;data:any;error?:boolean}[]; session_id: string; needs_clarification:boolean }
export type TimetableRecord = { id:string; day:string; subject:string; faculty:string; start_time:string; end_time:string; room:string; section:string; semester:string; sample_data:boolean }
export type CalendarRecord = { event_name:string; event_date:string; event_type:string; description:string; semester:string; sample_data:boolean }
export type FAQRecord = {id:string;category:string;question:string;answer:string;source:string;last_updated:string}
