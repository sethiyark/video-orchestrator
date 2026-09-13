import { useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Film, Layers3, Plus, ShieldCheck } from "lucide-react";
import { api, type Job } from "../lib/api";
import { Sidebar } from "../components/Sidebar";
import { NewVideoModal } from "../components/NewVideoModal";

export const Route = createFileRoute("/")({ component: Landing });

function Landing() {
  const navigate = useNavigate();
  const jobsQuery = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api<Job[]>("/jobs"),
    refetchInterval: 1000,
  });
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api<{ provider: string; database: string }>("/health"),
    refetchInterval: 15000,
  });
  const isLocal = health.data?.provider === "local";
  const jobs = jobsQuery.data ?? [];
  const [showForm, setShowForm] = useState(false);
  const waiting = jobs.filter((j) => j.status === "awaiting_approval").length;
  const active = jobs.filter((j) =>
    ["queued", "running"].includes(j.status),
  ).length;
  return (
    <div className="app">
      <Sidebar active="none" waitingCount={waiting} health={health.data} />
      <main>
        <header>
          <span>
            Workspace <span className="slash">/</span> Home
          </span>
          <span className="mode">
            <span className="mock-dot" />{" "}
            {isLocal ? "Local model mode" : "Development mode"}
          </span>
        </header>
        <div className="content">
          <section className="hero">
            <div className="eyebrow">YOUR PRODUCTION DESK</div>
            <h1>Welcome back. Ideas in. Videos out.</h1>
            <p>Keep every step of your next video in one place.</p>
            <button className="primary" onClick={() => setShowForm(true)}>
              <Plus size={17} /> New video
            </button>
          </section>
          <section className="stats">
            <article>
              <span>
                Total videos <Film size={17} />
              </span>
              <strong>{jobs.length.toString().padStart(2, "0")}</strong>
              <small>In your production workspace</small>
            </article>
            <article>
              <span>
                In production <Layers3 size={17} />
              </span>
              <strong>{active.toString().padStart(2, "0")}</strong>
              <small>Sequential processing</small>
            </article>
            <article>
              <span>
                Ready for review <ShieldCheck size={17} />
              </span>
              <strong className="accent">
                {waiting.toString().padStart(2, "0")}
              </strong>
              <small>Your approval is the final step</small>
            </article>
          </section>
        </div>
      </main>
      {showForm && (
        <NewVideoModal
          isLocal={isLocal}
          onClose={() => setShowForm(false)}
          onCreated={(job) => {
            setShowForm(false);
            void navigate({
              to: "/production/$jobId",
              params: { jobId: job.id },
            });
          }}
        />
      )}
    </div>
  );
}
