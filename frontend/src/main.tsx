import { QueryClient, QueryClientProvider, useMutation, useQuery } from "@tanstack/react-query";
import { createRoot } from "react-dom/client";
import { Link, BrowserRouter, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { FormEvent, useState } from "react";
import "./styles.css";

type Status = "PENDING" | "READY" | "CONDITIONAL" | "BLOCKED" | "INCONCLUSIVE";
type Analysis = { id: string; status: Status; report: { title?: string; decision?: Status; summary?: string; rules?: Rule[]; limitations?: string[]; findings?: unknown; fix?: unknown; validations?: unknown; acceptance_criteria?: unknown }; error?: string };
type Rule = { id: string; outcome: "PASS" | "FAIL" | "UNKNOWN"; message: string };
const request = async <T,>(path: string, options?: RequestInit): Promise<T> => {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error((await response.json()).detail ?? "No fue posible completar la solicitud.");
  return response.json() as Promise<T>;
};

function Header() {
  return <header><Link to="/" className="wordmark">PR/QA <b>GATE</b></Link><nav><Link to="/">Nuevo análisis</Link><Link to="/analyses">Historial</Link><span>solo lectura</span></nav></header>;
}
function NewAnalysis() {
  const navigate = useNavigate();
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const mutation = useMutation({ mutationFn: () => request<{ analysis_id: string }>("/api/v1/analyses", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ pull_request_url: url, model_profile_id: "openai-small", validation_profile_id: "python-demo", acceptance_criteria: [] }) }), onSuccess: ({ analysis_id }) => navigate(`/analyses/${analysis_id}`), onError: (reason: Error) => setError(reason.message) });
  const submit = (event: FormEvent) => { event.preventDefault(); setError(""); mutation.mutate(); };
  return <main className="landing"><p className="eyebrow">PR → QA / evidence first</p><h1>Decidir con pruebas,<br /><i>no con intuición.</i></h1><p className="lede">Analiza un pull request de GitHub, valida una corrección en aislamiento y aplica una política trazable.</p><form onSubmit={submit}><label htmlFor="pr-url">URL del pull request</label><div className="input-row"><input id="pr-url" type="url" required placeholder="https://github.com/owner/repo/pull/42" value={url} onChange={(event) => setUrl(event.target.value)} /><button disabled={mutation.isPending}>{mutation.isPending ? "Iniciando..." : "Analizar PR"}</button></div>{error && <p className="error" role="alert">{error}</p>}</form><aside><b>Alcance controlado</b><span>GitHub read-only · comandos administrados · sin secretos en el navegador</span></aside></main>;
}
function Decision({ status }: { status: Status }) { return <span className={`decision ${status.toLowerCase()}`}>{status}</span>; }
function Report() {
  const { id = "" } = useParams();
  const query = useQuery({ queryKey: ["analysis", id], queryFn: () => request<Analysis>(`/api/v1/analyses/${id}`), refetchInterval: (data) => data.state.data?.status === "PENDING" ? 1500 : false });
  if (query.isPending) return <main className="report"><p>Recuperando informe...</p></main>;
  if (query.isError) return <main className="report"><p className="error">No se pudo recuperar el informe.</p></main>;
  const analysis = query.data; const decision = analysis.report.decision ?? analysis.status;
  return <main className="report"><p className="eyebrow">ANÁLISIS / {id.slice(0, 8)}</p><section className="decision-panel"><Decision status={decision}/><div><h1>{analysis.report.title ?? "Análisis en curso"}</h1><p>{analysis.report.summary ?? analysis.error ?? "Esperando evidencia del workflow."}</p></div></section><section><h2>Controles de política</h2><div className="rules">{analysis.report.rules?.map((rule) => <div className="rule" key={rule.id}><span>{rule.id}</span><b className={rule.outcome.toLowerCase()}>{rule.outcome}</b><p>{rule.message}</p></div>) ?? <p>No hay controles disponibles todavía.</p>}</div></section><Evidence title="Hallazgos" value={analysis.report.findings} /><Evidence title="Corrección propuesta" value={analysis.report.fix} /><Evidence title="Validaciones" value={analysis.report.validations} /><Evidence title="Criterios de aceptación" value={analysis.report.acceptance_criteria} /><section><h2>Limitaciones y acciones</h2>{analysis.report.limitations?.map((item) => <p className="note" key={item}>{item}</p>) ?? <p className="note">{analysis.error ?? "Sin limitaciones registradas."}</p>}</section></main>;
}
function Evidence({ title, value }: { title: string; value: unknown }) { if (value === undefined || value === null) return null; return <section><h2>{title}</h2><pre className="evidence">{JSON.stringify(value, null, 2)}</pre></section>; }
function History() {
  const query = useQuery({ queryKey: ["analyses"], queryFn: () => request<Array<{ id: string; url: string; status: Status; created_at: string }>>("/api/v1/analyses") });
  return <main className="report"><p className="eyebrow">REGISTRO PERSISTENTE</p><h1>Historial de análisis</h1><section className="history">{query.data?.map((item) => <Link key={item.id} to={`/analyses/${item.id}`}><Decision status={item.status}/><span>{item.url}</span><time>{new Date(item.created_at).toLocaleString()}</time></Link>) ?? <p>{query.isPending ? "Cargando..." : "Aún no hay análisis."}</p>}</section></main>;
}
export function App() { return <><Header /><Routes><Route path="/" element={<NewAnalysis />} /><Route path="/analyses" element={<History />} /><Route path="/analyses/:id" element={<Report />} /></Routes></>; }
const client = new QueryClient();
document.documentElement.lang = "es";
const root = document.getElementById("root");
if (root) {
  createRoot(root).render(<BrowserRouter><QueryClientProvider client={client}><App /></QueryClientProvider></BrowserRouter>);
}
