// Local OpenAPI-shaped contract. API consumers import types only from this module.
export type DecisionStatus = "PENDING" | "RUNNING" | "READY" | "CONDITIONAL" | "BLOCKED" | "INCONCLUSIVE";
export type RuleOutcome = "PASS" | "FAIL" | "UNKNOWN";

export interface ModelProfile { id: string; provider: string; model: string; enabled: boolean }
export interface ValidationProfile { id: string }
export interface AcceptanceCriterion { id: string; text: string; required: boolean }
export interface CreateAnalysisRequest {
  pull_request_url: string;
  model_profile_id: string;
  validation_profile_id: string;
  acceptance_criteria: AcceptanceCriterion[];
}
export interface AnalysisCreated { analysis_id: string; status: DecisionStatus; deduplicated: boolean }
export interface RunEvent { sequence: number; node: string; message: string; created_at?: string }
export interface Rule { id: string; outcome: RuleOutcome; message: string }
export interface Finding {
  title: string; category: string; severity: string; file_path: string; start_line: number; end_line: number;
  evidence_excerpt: string; explanation: string; impact: string; recommended_action: string; confidence: number;
}
export interface Fix { summary: string; patch: string; regression_test_patch: string; modified_paths: string[]; assumptions: string[] }
export interface ValidationResult { command_name?: string; exit_code?: number | null; stdout?: string; stderr?: string; timed_out?: boolean; infrastructure_error?: boolean }
export interface CriterionResult { id: string; text: string; required: boolean; status: string; evidence: string[] }
export interface Decision { status: DecisionStatus; summary: string; policy_version: string; rules: Rule[] }
export interface AnalysisReport {
  analysis_id?: string; head_sha?: string | null; decision?: Decision; findings?: { summary?: string; findings?: Finding[] };
  fix?: Fix | null; validations?: { baseline?: { result?: ValidationResult; reproduced?: boolean | null }; candidate?: { results?: ValidationResult[]; regression_fixed?: boolean | null; suite_passed?: boolean | null } };
  acceptance_criteria?: CriterionResult[]; errors?: { code: string; message: string }[]; limitations?: string[];
}
export interface Analysis { id: string; status: DecisionStatus; report: AnalysisReport; error: string | null; created_at: string; finished_at: string | null; duration_ms: number | null; input_tokens: number | null; output_tokens: number | null; estimated_cost: number | null; model_profile_id: string; validation_profile_id: string }
export interface HistoryItem { id: string; pull_request_url: string; status: DecisionStatus; model_profile_id: string; head_sha: string | null; created_at: string; duration_ms: number | null }
export interface Problem { title: string; detail: string; status: number }
