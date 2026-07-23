import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { App } from "./main";

describe("App", () => {
  it("renders the analysis form and navigates to history", async () => {
    const view = render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={["/"]}>
          <App />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(screen.getByRole("heading", { name: /decidir con pruebas/i })).toBeInTheDocument();
    await screen.findByRole("link", { name: "Historial" }).then((link) => link.click());

    expect(await screen.findByRole("heading", { name: "Historial de análisis" })).toBeInTheDocument();
    view.unmount();
  });
});
