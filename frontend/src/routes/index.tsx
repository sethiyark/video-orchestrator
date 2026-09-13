import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Clapperboard,
  Film,
  Layers3,
  Play,
  Plus,
  ShieldCheck,
} from "lucide-react";
import { api, type Job } from "../lib/api";
import { label } from "../lib/format";
import { Sidebar } from "../components/Sidebar";
export const Route = createFileRoute("/")({ component: Dashboard });
function Dashboard() {
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
  const [filter, setFilter] = useState<"all" | "review" | "completed">("all");
  const [showCompleted, setShowCompleted] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [brief, setBrief] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [sourceExcerpt, setSourceExcerpt] = useState("");
  const refresh = () => client.invalidateQueries({ queryKey: ["jobs"] });
  const create = useMutation({
    mutationFn: () =>
      api<Job>("/jobs", {
        title,
        brief,
        sources: sourceUrl
          ? [
              {
                id: "source_1",
                title: "User supplied source",
                url: sourceUrl,
                excerpt: sourceExcerpt,
              },
            ]
          : [],
      }),
    onSuccess: () => {
      setShowForm(false);
      setTitle("");
      setBrief("");
      setSourceUrl("");
      setSourceExcerpt("");
      void refresh();
    },
  });
  const waiting = jobs.filter((j) => j.status === "awaiting_approval").length;
  const active = jobs.filter((j) =>
    ["queued", "running"].includes(j.status),
  ).length;
  const visible = jobs.filter((j) => {
    if (filter === "review") return j.status === "awaiting_approval";
    if (filter === "completed") return j.status === "completed";
    return showCompleted || j.status !== "completed";
  });
  return (
    <div className="app">
      <Sidebar
        active={filter}
        waitingCount={waiting}
        health={health.data}
        onTab={setFilter}
      />
      <main>
        <header>
          <span>
            Workspace <span className="slash">/</span> Production
          </span>
          <span className="mode">
            <span className="mock-dot" />{" "}
            {isLocal ? "Local model mode" : "Development mode"}
          </span>
        </header>
        <div className="content">
          <div className="heading">
            <div>
              <div className="eyebrow">YOUR PRODUCTION DESK</div>
              <h1>Ideas in. Videos out.</h1>
              <p>Keep every step of your next video in one place.</p>
            </div>
            <button className="primary" onClick={() => setShowForm(true)}>
              <Plus size={17} /> New video
            </button>
          </div>
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
          <div className="section-title">
            <h2>
              {filter === "review"
                ? "Review queue"
                : filter === "completed"
                  ? "Completed videos"
                  : "Video pipeline"}{" "}
              <span>{visible.length}</span>
            </h2>
            <span className="muted">
              {isLocal
                ? "Local models · Rendering and upload not connected"
                : "Mock workflow · No real uploads"}
            </span>
          </div>
          {filter === "all" && (
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
                <h2>
                  {filter === "all"
                    ? "Your next story starts here"
                    : "Nothing here yet"}
                </h2>
                <p>
                  {filter === "all"
                    ? "Add a video idea and watch it move from research to review."
                    : "Videos will appear here as they move through the pipeline."}
                </p>
                {filter === "all" && (
                  <button className="primary" onClick={() => setShowForm(true)}>
                    <Plus size={16} /> Create your first video
                  </button>
                )}
              </div>
            )}
          <div className="jobs">
            {visible.map((job) => (
              <Link
                key={job.id}
                to="/production/$jobId"
                params={{ jobId: job.id }}
                className="job-card"
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
                    {job.stages.filter((s) => s.status === "completed").length}{" "}
                    / {job.stages.length} stages <ArrowUpRight size={14} />
                  </small>
                </div>
              </Link>
            ))}
          </div>
          <div className="note">
            <ShieldCheck size={18} />
            <span>
              You stay in control. Every video pauses for your approval before
              the upload stage.
            </span>
          </div>
          <div className="bottom-line">
            A little less busywork. A lot more creating.
            <span>POWERED BY LOCAL WORKFLOWS</span>
          </div>
        </div>
      </main>
      {showForm && (
        <div className="overlay">
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="new-title"
            className="modal"
          >
            <div className="eyebrow">START SOMETHING GOOD</div>
            <h2 id="new-title">New video</h2>
            <p>Give your next explainer a direction.</p>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                create.mutate();
              }}
            >
              <label htmlFor="title">Video title</label>
              <input
                id="title"
                autoFocus
                required
                maxLength={160}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Why the internet needs DNS"
              />
              <label htmlFor="brief">
                Creative brief <span>(optional)</span>
              </label>
              <textarea
                id="brief"
                rows={4}
                maxLength={5000}
                value={brief}
                onChange={(e) => setBrief(e.target.value)}
                placeholder="Audience, key points, tone, and target length…"
              />
              <label htmlFor="source-url">
                Source URL {isLocal ? "(required)" : "(optional)"}
              </label>
              <input
                id="source-url"
                type="url"
                required={isLocal || !!sourceExcerpt}
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
                placeholder="https://example.com/technical-reference"
              />
              <label htmlFor="source-excerpt">Source excerpt</label>
              <textarea
                id="source-excerpt"
                rows={5}
                minLength={20}
                maxLength={6000}
                required={isLocal || !!sourceUrl}
                value={sourceExcerpt}
                onChange={(e) => setSourceExcerpt(e.target.value)}
                placeholder="Paste the evidence the research and verification models should use…"
              />
              <p className="muted">
                Local research uses the supplied excerpt. It does not fetch the
                URL. More sources can be supplied through the API.
              </p>
              <p className="muted">
                Starts as a draft. Run the pipeline when you're ready.
              </p>
              {create.error && (
                <p role="alert" className="error">
                  {create.error.message}
                </p>
              )}
              <div className="actions">
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setShowForm(false)}
                >
                  Cancel
                </button>
                <button
                  className="primary"
                  disabled={!title.trim() || create.isPending}
                >
                  {create.isPending ? "Creating…" : "Create video"}
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}
