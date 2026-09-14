import { useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Clapperboard,
  Play,
  Plus,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { api, apiDelete, type Job } from "../lib/api";
import { label } from "../lib/format";
import { Sidebar, type SidebarTab } from "./Sidebar";
import { NewVideoModal } from "./NewVideoModal";

export function JobsPage({
  tab,
  heading,
  filterJob,
  emptyTitle,
  emptyBody,
  showCompletedToggle = false,
  showNewVideoButton = false,
}: {
  tab: Exclude<SidebarTab, "none">;
  heading: string;
  filterJob: (job: Job, showCompleted: boolean) => boolean;
  emptyTitle: string;
  emptyBody: string;
  showCompletedToggle?: boolean;
  showNewVideoButton?: boolean;
}) {
  const navigate = useNavigate();
  const client = useQueryClient();
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
  const [showCompleted, setShowCompleted] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const waiting = jobs.filter((j) => j.status === "awaiting_approval").length;
  const visible = jobs.filter((j) => filterJob(j, showCompleted));
  const deleteJob = useMutation({
    mutationFn: (id: string) => apiDelete(`/jobs/${id}`),
    onSuccess: () => client.invalidateQueries({ queryKey: ["jobs"] }),
  });
  return (
    <div className="app">
      <Sidebar active={tab} waitingCount={waiting} health={health.data} />
      <main>
        <header>
          <span>
            Workspace <span className="slash">/</span> {heading}
          </span>
          <span className="mode">
            <span className="mock-dot" />{" "}
            {isLocal ? "Local model mode" : "Development mode"}
          </span>
        </header>
        <div className="content">
          <div className="section-title">
            <h2>
              {heading} <span>{visible.length}</span>
            </h2>
            <div className="section-title-actions">
              <span className="muted">
                {isLocal
                  ? "Local models · Rendering and upload not connected"
                  : "Mock workflow · No real uploads"}
              </span>
              {showNewVideoButton && (
                <button className="primary" onClick={() => setShowForm(true)}>
                  <Plus size={17} /> New video
                </button>
              )}
            </div>
          </div>
          {showCompletedToggle && (
            <label className="show-completed">
              <input
                type="checkbox"
                checked={showCompleted}
                onChange={(e) => setShowCompleted(e.target.checked)}
              />
              Show completed
            </label>
          )}
          {jobsQuery.isError && (
            <div role="alert" className="error">
              Cannot reach the backend. Start FastAPI on port 8091.{" "}
              <button onClick={() => void jobsQuery.refetch()}>Retry</button>
            </div>
          )}
          {deleteJob.error && (
            <div role="alert" className="error">
              {deleteJob.error.message}
            </div>
          )}
          {jobsQuery.isPending && (
            <div className="empty">Loading your workspace…</div>
          )}
          {!jobsQuery.isPending &&
            !jobsQuery.isError &&
            visible.length === 0 && (
              <div className="empty">
                <div className="empty-icon">
                  <Clapperboard size={32} />
                </div>
                <h2>{emptyTitle}</h2>
                <p>{emptyBody}</p>
                {showNewVideoButton && (
                  <button className="primary" onClick={() => setShowForm(true)}>
                    <Plus size={16} /> Create your first video
                  </button>
                )}
              </div>
            )}
          <div className="jobs">
            {visible.map((job) => (
              <div key={job.id} className="job-card">
                <Link
                  to="/production/$jobId"
                  params={{ jobId: job.id }}
                  className="job-card-link"
                >
                  <div className="job-art">
                    <Play size={25} />
                    <span>EXPLAINER</span>
                  </div>
                  <div className="job-info">
                    <span className={`badge ${job.status}`}>
                      {label(job.status)}
                    </span>
                    <h3>{job.title}</h3>
                    <p>{job.brief || "No creative brief added"}</p>
                    <div className="progress">
                      <div
                        style={{
                          width: `${(job.stages.filter((s) => s.status === "completed").length / job.stages.length) * 100}%`,
                        }}
                      />
                    </div>
                    <small>
                      {
                        job.stages.filter((s) => s.status === "completed")
                          .length
                      }{" "}
                      / {job.stages.length} stages <ArrowUpRight size={14} />
                    </small>
                  </div>
                </Link>
                <button
                  type="button"
                  className="job-delete"
                  title="Delete pipeline"
                  disabled={deleteJob.isPending}
                  onClick={() => {
                    if (
                      window.confirm(
                        `Delete "${job.title}"? This cannot be undone.`,
                      )
                    )
                      deleteJob.mutate(job.id);
                  }}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
          <div className="note">
            <ShieldCheck size={18} />
            <span>
              You stay in control. Every video pauses for your approval before
              the upload stage.
            </span>
          </div>
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
