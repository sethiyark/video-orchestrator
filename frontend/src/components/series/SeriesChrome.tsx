import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type Job } from "../../lib/api";
import { Sidebar } from "../Sidebar";

/** Sidebar + header shared by the series pages; exposes jobs and health. */
export function useWorkspace() {
  const jobs = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api<Job[]>("/jobs"),
    refetchInterval: 1000,
  });
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api<{ provider: string; database: string }>("/health"),
    refetchInterval: 15000,
  });
  return { jobs, health, isLocal: health.data?.provider === "local" };
}

export function SeriesChrome({
  crumb,
  children,
}: {
  crumb: ReactNode;
  children: ReactNode;
}) {
  const { jobs, health } = useWorkspace();
  const waiting =
    jobs.data?.filter((job) => job.status === "awaiting_approval").length ?? 0;
  return (
    <div className="app">
      <Sidebar active="series" waitingCount={waiting} health={health.data} />
      <main>
        <header>
          <span>
            Workspace <span className="slash">/</span> {crumb}
          </span>
        </header>
        <div className="content">{children}</div>
      </main>
    </div>
  );
}
