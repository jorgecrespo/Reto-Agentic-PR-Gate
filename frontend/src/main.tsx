import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./app";
import "./styles.css";

export { App } from "./app";

const root = document.getElementById("root");
if (root) createRoot(root).render(<BrowserRouter><QueryClientProvider client={new QueryClient()}><App /></QueryClientProvider></BrowserRouter>);
