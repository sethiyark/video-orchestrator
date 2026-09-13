import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { ModelPanel } from "../components/ModelPanel";
import { Sidebar } from "../components/Sidebar";

export const Route = createFileRoute("/configuration")({
  component: Configuration,
});

function Configuration() {
  const jobsQuery = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api<{ status: string }[]>("/jobs"),
    refetchInterval: 1000,
  });
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api<{ provider: string; database: string }>("/health"),
    refetchInterval: 15000,
  });
  const waiting =
    jobsQuery.data?.filter((j) => j.status === "awaiting_approval").length ??
    0;
  return (
    <div className="app">
      <Sidebar active="configuration" waitingCount={waiting} health={health.data} />
      <main>
        <header>
          <span>
            Workspace <span className="slash">/</span> Configuration
          </span>
        </header>
        <div className="content">
          <div className="heading">
            <div>
              <div className="eyebrow">MODELS &amp; RUNTIMES</div>
              <h1>Configuration</h1>
              <p>Manage the models that power your production pipeline.</p>
            </div>
          </div>
          <ModelPanel />
        </div>
      </main>
    </div>
  );
}
