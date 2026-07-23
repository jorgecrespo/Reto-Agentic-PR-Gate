export type GateStatus = "READY" | "CONDITIONAL" | "BLOCKED" | "INCONCLUSIVE" | "PENDING";

export function statusLabel(status: GateStatus): string {
  const labels: Record<GateStatus, string> = {
    READY: "Puede avanzar a QA",
    CONDITIONAL: "Requiere una condición explícita",
    BLOCKED: "Tiene bloqueos comprobados",
    INCONCLUSIVE: "No existe evidencia suficiente",
    PENDING: "Análisis en progreso",
  };
  return labels[status];
}
