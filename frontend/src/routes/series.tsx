import { useState } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowUpRight, BookOpen, Plus } from "lucide-react";
import { api, type Series } from "../lib/api";
import { SeriesChrome, useWorkspace } from "../components/series/SeriesChrome";

export const Route = createFileRoute("/series")({ component: SeriesList });

function SeriesList() {
  const navigate = useNavigate();
  const { jobs } = useWorkspace();
  const series = useQuery({
    queryKey: ["series"],
    queryFn: () => api<Series[]>("/series"),
  });
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const create = useMutation({
    mutationFn: () => api<Series>("/series", { name, description }),
    onSuccess: (created) =>
      void navigate({
        to: "/series/$seriesId",
        params: { seriesId: created.id },
      }),
  });
  const items = series.data ?? [];
  const videoCount = (id: string) =>
    jobs.data?.filter((job) => job.series_id === id).length ?? 0;
  return (
    <SeriesChrome crumb="Series">
      <div className="section-title">
        <h2>
          Series <span>{items.length}</span>
        </h2>
        <div className="section-title-actions">
          <span className="muted">
            Shared bibles, themes, and idea backlogs
          </span>
          <button className="primary" onClick={() => setShowForm(true)}>
            <Plus size={17} /> New series
          </button>
        </div>
      </div>
      {series.isError && (
        <div role="alert" className="error">
          Cannot reach the backend. Start FastAPI on port 8091.
        </div>
      )}
      {series.isPending && <div className="empty">Loading series…</div>}
      {!series.isPending && !series.isError && items.length === 0 && (
        <div className="empty">
          <div className="empty-icon">
            <BookOpen size={32} />
          </div>
          <h2>Give your videos a shared voice</h2>
          <p>
            A series holds the style bible, themes, and idea backlog your
            pipelines draw from.
          </p>
          <button className="primary" onClick={() => setShowForm(true)}>
            <Plus size={16} /> Create your first series
          </button>
        </div>
      )}
      <div className="series-grid">
        {items.map((item) => (
          <Link
            key={item.id}
            to="/series/$seriesId"
            params={{ seriesId: item.id }}
            className="series-card"
          >
            <span className="series-icon">
              <BookOpen size={20} />
            </span>
            <h3>{item.name}</h3>
            <p>{item.description || "No description yet"}</p>
            <small>
              {videoCount(item.id)} videos · /{item.slug}{" "}
              <ArrowUpRight size={14} />
            </small>
          </Link>
        ))}
      </div>
      {showForm && (
        <div className="overlay">
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="series-new-title"
            className="modal"
          >
            <div className="eyebrow">SHARED PROJECT</div>
            <h2 id="series-new-title">New series</h2>
            <p>Videos in a series share a style bible, themes, and ideas.</p>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                create.mutate();
              }}
            >
              <label htmlFor="series-name">Name</label>
              <input
                id="series-name"
                autoFocus
                required
                maxLength={160}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Systems Deep Dives"
              />
              <label htmlFor="series-description">
                Description <span>(optional)</span>
              </label>
              <textarea
                id="series-description"
                rows={3}
                maxLength={5000}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="What ties these videos together?"
              />
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
                  disabled={!name.trim() || create.isPending}
                >
                  {create.isPending ? "Creating…" : "Create series"}
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
    </SeriesChrome>
  );
}
