// Local OpenAPI-shaped contract. API consumers import types only from this module.
export type DecisionStatus = "PENDING" | "RUNNING" | "READY" | "CONDITIONAL" | "BLOCKED" | "INCONCLUSIVE";
export type RuleOutcome = "PASS" | "FAIL" | "UNKNOWN";

export interface ModelProfile { id: string; provider: string; model: string; enabled: boolean }
export interface ValidationProfile { id: string }
export interface AcceptanceCriterion { id: string; text: string; required: boolean; validation_tests?: string[] }
export interface CreateAnalysisRequest {
  pull_request_url: string;
  model_profile_id: string;
  validation_profile_id: string;
  acceptance_criteria: AcceptanceCriterion[];
}
export interface AnalysisCreated { analysis_id: string; status: DecisionStatus; deduplicated: boolean }
export interface RunEvent { sequence: number; node: string; message: string; created_at?: string }
export interface Rule { id: string; outcome: RuleOutcome; message: string; evidence_ids?: string[] }
export interface Finding {
  title: string; category: string; severity: string; file_path: string; start_line: number; end_line: number;
  evidence_excerpt: string; explanation: string; impact: string; recommended_action: string; confidence: number;
}
export interface Fix { summary: string; patch: string; regression_test_patch: string; regression_test_name?: string | null; modified_paths: string[]; assumptions: string[] }
export interface ValidationResult { command_name?: string; command?: string[]; exit_code?: number | null; stdout?: string; stderr?: string; timed_out?: boolean; infrastructure_error?: boolean; classification?: string; executed_tests?: string[]; failed_tests?: string[] }
export interface CriterionResult { id: string; text: string; required: boolean; status: string; evidence: string[]; reason?: string }
export interface PullRequestSummary { url?: string | null; title?: string | null; base_sha?: string | null; head_sha?: string | null; draft?: boolean | null; modified_files: string[] }
export interface SecretEvidence { path: string; start_line: number; end_line: number; kinds: string[] }
export interface NotExecutedControl { id: string; label: string; reason: string }
export interface ExecutionSummary { llm?: { status: "EXECUTED" | "NOT_EXECUTED"; reason?: string | null }; candidate_validation?: { status: "EXECUTED" | "NOT_EXECUTED"; reason?: string | null }; not_executed_controls?: NotExecutedControl[] }
export interface Decision { status: DecisionStatus; summary: string; policy_version: string; rules: Rule[]; blocking_reasons?: Rule[]; warnings?: Rule[]; not_evaluated_rules?: Rule[]; required_actions?: string[] }
export interface AnalysisReport {
  analysis_id?: string; head_sha?: string | null; decision?: Decision; findings?: { summary?: string; findings?: Finding[] };
  fix?: Fix | null; validations?: { original?: { results?: ValidationResult[]; tests_passed?: boolean | null; lint_passed?: boolean | null }; baseline?: { result?: ValidationResult; reproduced?: boolean | null; target_test?: string | null }; candidate?: { status?: "VALIDATED" | "REJECTED" | "INCONCLUSIVE" | "NOT_PROPOSED"; results?: ValidationResult[]; target_test?: string | null; target_test_executed?: boolean | null; regression_fixed?: boolean | null; tests_passed?: boolean | null; lint_passed?: boolean | null } };
  pull_request?: PullRequestSummary; acceptance_criteria?: CriterionResult[]; secret_evidence?: SecretEvidence[]; execution?: ExecutionSummary; errors?: { code: string; message: string }[]; limitations?: string[];
}
export interface Analysis { id: string; status: DecisionStatus; report: AnalysisReport; error: string | null; created_at: string; finished_at: string | null; duration_ms: number | null; input_tokens: number | null; output_tokens: number | null; estimated_cost: number | null; model_profile_id: string; validation_profile_id: string }
export interface HistoryItem { id: string; pull_request_url: string; status: DecisionStatus; model_profile_id: string; head_sha: string | null; created_at: string; duration_ms: number | null }
export interface Problem { title: string; detail: string; status: number }
