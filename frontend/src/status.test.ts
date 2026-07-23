import { describe, expect, it } from "vitest";
import { statusLabel } from "./status";

describe("statusLabel", () => {
  it("explains ready, blocked and inconclusive distinctly", () => {
    expect(statusLabel("READY")).toContain("QA");
    expect(statusLabel("BLOCKED")).toContain("bloqueos");
    expect(statusLabel("INCONCLUSIVE")).toContain("evidencia");
  });
});
