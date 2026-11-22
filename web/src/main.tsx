import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router";

import Layout from "./components/Layout";
import { Spinner } from "./components/ui";
import "./index.css";
import NotFound from "./pages/NotFound";

// Pages load on demand, so Live Monitor doesn't download the charting library.
const LiveMonitor = lazy(() => import("./pages/LiveMonitor"));
const Analyze = lazy(() => import("./pages/Analyze"));
const JobDetail = lazy(() => import("./pages/JobDetail"));
const Violations = lazy(() => import("./pages/Violations"));
const ModelPage = lazy(() => import("./pages/Model"));
const page = (el: React.ReactNode) => <Suspense fallback={<Spinner label="Loading…" />}>{el}</Suspense>;

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } });

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: "/", element: page(<LiveMonitor />) },
      { path: "/analyze", element: page(<Analyze />) },
      { path: "/jobs/:id", element: page(<JobDetail />) },
      { path: "/violations", element: page(<Violations />) },
      { path: "/model", element: page(<ModelPage />) },
      { path: "*", element: <NotFound /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
