import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Check,
  Clapperboard,
  Cpu,
  Film,
  Layers3,
  Play,
  Plus,
  ShieldCheck,
} from "lucide-react";
import { api, type Job, artifactUrl } from "../lib/api";
import { ModelPanel } from "../components/ModelPanel";
export const Route = createFileRoute("/")({ component: Dashboard });
const label = (value: string) => value.replaceAll("_", " ");
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
  const [selected, setSelected] = useState<string | null>(null);
  const [filter, setFilter] = useState("all");
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [brief, setBrief] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [sourceExcerpt, setSourceExcerpt] = useState("");
  const current = jobs.find((job) => job.id === selected);
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
    onSuccess: (job) => {
      setSelected(job.id);
      setShowForm(false);
      setTitle("");
      setBrief("");
      setSourceUrl("");
      setSourceExcerpt("");
      void refresh();
    },
  });
  const action = useMutation({
    mutationFn: ({ id, action }: { id: string; action: string }) =>
      api<Job>(`/jobs/${id}/${action}`, {}),
    onSuccess: refresh,
  });
  const waiting = jobs.filter((j) => j.status === "awaiting_approval").length;
  const active = jobs.filter((j) =>
    ["queued", "running"].includes(j.status),
  ).length;
  const visible = jobs.filter(
    (j) =>
      filter === "all" ||
      (filter === "review"
        ? j.status === "awaiting_approval"
        : j.status === "completed"),
  );
  return (
    <div className="app">
      <aside className="sidebar">
        <a className="brand" href="/">
          <span className="brand-icon">
            <Clapperboard size={22} />
          </span>
          framecraft<span className="brand-dot">.</span>
        </a>
        <div className="workspace">
          <span className="avatar">S</span>
          <div>
            My studio<small>Single-channel workspace</small>
          </div>
        </div>
        <div className="nav-label">WORKSPACE</div>
        <button
          className={filter === "all" ? "nav active" : "nav"}
          onClick={() => setFilter("all")}
        >
          <Layers3 size={18} /> Production
        </button>
        <button
          className={filter === "review" ? "nav active" : "nav"}
          onClick={() => setFilter("review")}
        >
          <ShieldCheck size={18} /> Review queue{" "}
          <span className="count">{waiting}</span>
        </button>
        <button
          className={filter === "completed" ? "nav active" : "nav"}
          onClick={() => setFilter("completed")}
        >
          <Film size={18} /> Completed
        </button>
        <div className="local-card">
          <Cpu size={22} />
          <strong>Local by design</strong>
          <p>
            One workload at a time.
            <br />
            Built for your 8 GB GPU.
          </p>
          <span className="mock-dot" />{" "}
          {health.data
            ? `${health.data.provider} providers · ${health.data.database}`
            : "Checking backend…"}
        </div>
        <footer>FRAMECRAFT / v0.1</footer>
      </aside>
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
          <ModelPanel />
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
          {jobsQuery.isError && (
            <div role="alert" className="error">
              Cannot reach the backend. Start FastAPI on port 8000.{" "}
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
              <button
                key={job.id}
                className={`job-card ${selected === job.id ? "selected" : ""}`}
                onClick={() => {
                  setSelected(job.id);
                  action.reset();
                }}
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
              </button>
            ))}
          </div>
          <div className="note">
            <ShieldCheck size={18} />
            <span>
              You stay in control. Every video pauses for your approval before
              the upload stage.
            </span>
          </div>
          {current && (
            <section className="detail">
              <div className="detail-heading">
                <div className="min-width">
                  <div className="eyebrow">PRODUCTION DETAILS</div>
                  <h2>{current.title}</h2>
                </div>
                <div className="actions">
                  {["draft", "failed"].includes(current.status) && (
                    <button
                      className="primary"
                      disabled={action.isPending}
                      onClick={() =>
                        action.mutate({ id: current.id, action: "run" })
                      }
                    >
                      <Play size={15} />
                      {current.status === "failed"
                        ? "Retry pipeline"
                        : "Run pipeline"}
                    </button>
                  )}
                  {current.status === "awaiting_approval" && (
                    <button
                      className="primary"
                      disabled={action.isPending}
                      onClick={() =>
                        action.mutate({ id: current.id, action: "approve" })
                      }
                    >
                      <Check size={16} /> Approve mock upload
                    </button>
                  )}
                  <button
                    className="secondary"
                    onClick={() => setSelected(null)}
                  >
                    Close
                  </button>
                </div>
              </div>
              {current.status === "awaiting_approval" && (
                <div className="review-note">
                  Review the outputs below before approving. All outputs are
                  placeholders; no playable video has been generated.
                </div>
              )}
              {(current.error || action.error) && (
                <p role="alert" className="error">
                  {action.error?.message || current.error}
                </p>
              )}
              <div className="stages">
                {current.stages.map((stage, index) => (
                  <details key={stage.name}>
                    <summary>
                      <span className={`step ${stage.status}`}>
                        {stage.status === "completed" ? (
                          <Check size={14} />
                        ) : (
                          index + 1
                        )}
                      </span>
                      <strong>{label(stage.name)}</strong>
                      <span className={`badge ${stage.status}`}>
                        {stage.status}
                      </span>
                    </summary>
                    {stage.output ? (
                      <div>
                        <pre>{JSON.stringify(stage.output, null, 2)}</pre>
                        {typeof stage.output.artifact === "object" &&
                          stage.output.artifact &&
                          "id" in stage.output.artifact && (
                            <a
                              className="artifact-link"
                              href={artifactUrl(
                                current.id,
                                String(stage.output.artifact.id),
                              )}
                            >
                              Download stage JSON
                            </a>
                          )}
                        {typeof stage.output.audio === "object" &&
                          stage.output.audio &&
                          "id" in stage.output.audio && (
                            <a
                              className="artifact-link"
                              href={artifactUrl(
                                current.id,
                                String(stage.output.audio.id),
                              )}
                            >
                              Download narration WAV
                            </a>
                          )}
                      </div>
                    ) : (
                      <p className="muted">
                        Output will appear when this stage completes.
                      </p>
                    )}
                  </details>
                ))}
              </div>
            </section>
          )}
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
