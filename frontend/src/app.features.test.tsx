import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./app";

const blocked = {
  id: "analysis-1", status: "BLOCKED", error: null, created_at: "2026-01-01T00:00:00Z", finished_at: "2026-01-01T00:00:01Z", duration_ms: 1200, input_tokens: null, output_tokens: null, estimated_cost: null, model_profile_id: "openai-small", validation_profile_id: "python-demo",
  report: { pull_request: { url: "https://github.com/acme/shop/pull/1", title: "Bloqueo de precio", base_sha: "a".repeat(40), head_sha: "b".repeat(40), draft: false, modified_files: ["app/orders.py"] }, decision: { status: "BLOCKED", summary: "Existe un bloqueo verificable.", policy_version: "1.0.1", rules: [{ id: "GATE-005", outcome: "FAIL", message: "Hallazgo crítico.", evidence_ids: ["finding-1"] }], required_actions: ["Aplicar la corrección propuesta y repetir la suite."] }, findings: { findings: [{ title: "Precio controlado", category: "security", severity: "critical", file_path: "app/orders.py", start_line: 18, end_line: 18, evidence_excerpt: "total += item.unit_price", explanation: "Confía en el cliente.", impact: "Permite alterar precios.", recommended_action: "Usar catálogo.", confidence: 0.98 }] }, fix: { summary: "Usar catálogo", patch: "diff --git a/app/orders.py", regression_test_patch: "diff --git a/tests/test_orders.py", modified_paths: ["app/orders.py"], assumptions: [] }, validations: { baseline: { result: { exit_code: 1, stderr: "assertion failed" } }, candidate: { results: [{ exit_code: 0, stdout: "passed" }] } }, acceptance_criteria: [{ id: "AC-1", text: "El precio es vigente", required: true, status: "FAILED", evidence: ["baseline"] }] },
};

function response(body: unknown) { return Promise.resolve(new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } })); }
function renderApp(path = "/") { return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></QueryClientProvider>); }

afterEach(() => vi.unstubAllGlobals());

describe("frontend vertical slice", () => {
  it("loads profiles, submits analysis and navigates to the simulated report", async () => {
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path.includes("config/models")) return response({ models: [{ id: "gemini-small", provider: "gemini", model: "gemini-2.0-flash", enabled: true }, { id: "openai-small", provider: "openai", model: "gpt-4.1-mini", enabled: true }] });
      if (path.includes("validation-profiles")) return response({ validation_profiles: [{ id: "python-demo" }] });
      if (path === "/api/v1/analyses" && init?.method === "POST") return response({ analysis_id: "analysis-1", status: "PENDING", deduplicated: false });
      if (path.includes("analysis-1")) return response(blocked);
      return response({ items: [] });
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("EventSource", function EventSourceStub() {
      return { addEventListener: vi.fn(), close: vi.fn() };
    });
    renderApp();
    fireEvent.change(await screen.findByLabelText("URL del pull request"), { target: { value: "https://github.com/acme/shop/pull/1" } });
    fireEvent.click(screen.getByRole("button", { name: "Analizar PR" }));
    await screen.findByText("Existe un bloqueo verificable.");
    const submitted = JSON.parse(String(fetchMock.mock.calls.find(([path]) => path === "/api/v1/analyses")?.[1]?.body));
    expect(submitted.model_profile_id).toBe("gemini-small");
    expect(submitted.acceptance_criteria).toBeUndefined();
  });

  it("renders BLOCKED and its file evidence", async () => {
    vi.stubGlobal("fetch", vi.fn(() => response(blocked)));
    renderApp("/analyses/analysis-1");
    expect(await screen.findByText("BLOCKED")).toBeInTheDocument();
    expect(screen.getByText("total += item.unit_price")).toBeInTheDocument();
    expect(screen.getByText("GATE-005")).toBeInTheDocument();
    expect(screen.getByText("Resumen del PR")).toBeInTheDocument();
    expect(screen.getByText("Aplicar la corrección propuesta y repetir la suite.")).toBeInTheDocument();
  });

  it("explains a secret block without exposing its value", async () => {
    const secretBlocked = {
      ...blocked,
      report: {
        ...blocked.report,
        decision: { ...blocked.report.decision, summary: "Se detectó un secreto potencial en el cambio.", required_actions: ["Retirar el secreto potencial del cambio."] },
        secret_evidence: [{ path: "app/domain.py", start_line: 4, end_line: 4, kinds: ["demo_secret"] }],
        execution: { llm: { status: "NOT_EXECUTED", reason: "Omitido porque se detectó un secreto potencial en el cambio." }, candidate_validation: { status: "NOT_EXECUTED", reason: "Omitido porque se detectó un secreto potencial en el cambio." }, not_executed_controls: [{ id: "GATE-003", label: "Los tests obligatorios deben ejecutarse.", reason: "Omitido porque se detectó un secreto potencial en el cambio." }] },
      },
    };
    vi.stubGlobal("fetch", vi.fn(() => response(secretBlocked)));
    renderApp("/analyses/analysis-1");
    expect(await screen.findByText("Secretos detectados")).toBeInTheDocument();
    expect(screen.getByText("LLM no ejecutado: Omitido porque se detectó un secreto potencial en el cambio.")).toBeInTheDocument();
    expect(screen.getByText("Retirar el secreto potencial del cambio.")).toBeInTheDocument();
    expect(screen.queryByText("sk-test-1234567890abcdef")).not.toBeInTheDocument();
  });

  it("explains INCONCLUSIVE without presenting it as ready", async () => {
    vi.stubGlobal("fetch", vi.fn(() => response({ ...blocked, status: "INCONCLUSIVE", report: { ...blocked.report, decision: { ...blocked.report.decision, status: "INCONCLUSIVE", summary: "No se ejecutaron controles obligatorios." } } })));
    renderApp("/analyses/analysis-1");
    expect(await screen.findByText("Evidencia insuficiente")).toBeInTheDocument();
    expect(screen.getByText("INCONCLUSIVE")).toBeInTheDocument();
  });

  it("shows an empty history after a filtered query", async () => {
    vi.stubGlobal("fetch", vi.fn(() => response({ items: [] })));
    renderApp("/analyses");
    fireEvent.change(screen.getByLabelText("Filtrar por decisión"), { target: { value: "BLOCKED" } });
    await waitFor(() => expect(screen.getByText("Aún no hay análisis para este filtro.")).toBeInTheDocument());
  });
});
