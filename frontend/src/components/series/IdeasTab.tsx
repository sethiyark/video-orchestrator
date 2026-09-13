import { useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, Play, Plus, RotateCcw, Trash2 } from "lucide-react";
import {
  api,
  apiDelete,
  apiSend,
  type Idea,
  type Job,
  type Theme,
} from "../../lib/api";
import { label } from "../../lib/format";
import { LibrarySourcePicker } from "./LibrarySourcePicker";

export function IdeasTab({
  seriesId,
  isLocal,
}: {
  seriesId: string;
  isLocal: boolean;
}) {
  const client = useQueryClient();
  const ideas = useQuery({
    queryKey: ["series", seriesId, "ideas"],
    queryFn: () => api<Idea[]>(`/series/${seriesId}/ideas`),
    refetchInterval: 3000,
  });
  const themes = useQuery({
    queryKey: ["series", seriesId, "themes"],
    queryFn: () => api<Theme[]>(`/series/${seriesId}/themes`),
  });
  const [showForm, setShowForm] = useState(false);
  const [starting, setStarting] = useState<Idea | null>(null);
  const refresh = () =>
    client.invalidateQueries({ queryKey: ["series", seriesId, "ideas"] });
  const update = useMutation({
    mutationFn: ({ id, status }: { id: string; status: Idea["status"] }) =>
      apiSend<Idea>(`/series/${seriesId}/ideas/${id}`, "PATCH", { status }),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: (id: string) => apiDelete(`/series/${seriesId}/ideas/${id}`),
    onSuccess: refresh,
  });
  const themeName = (id: string | null) =>
    themes.data?.find((theme) => theme.id === id)?.name;
  const items = ideas.data ?? [];
  const error = update.error || remove.error;
  return (
    <div>
      <div className="tab-toolbar">
        <p className="muted">
          Backlog of video ideas. Starting one creates a draft video that
          snapshots the series bible.
        </p>
        <button className="primary" onClick={() => setShowForm(true)}>
          <Plus size={16} /> New idea
        </button>
      </div>
      {error && (
        <div role="alert" className="error">
          {error.message}
        </div>
      )}
      {ideas.isPending && <div className="empty">Loading ideas…</div>}
      {!ideas.isPending && items.length === 0 && (
        <div className="empty">
          <h2>The backlog is empty</h2>
          <p>Jot down the next few explainers this series should cover.</p>
        </div>
      )}
      <div className="card-list">
        {items.map((idea) => (
          <article key={idea.id} className="list-card">
            <div className="min-width">
              <span className={`badge ${idea.status}`}>{idea.status}</span>
              {themeName(idea.theme_id) && (
                <span className="badge theme">{themeName(idea.theme_id)}</span>
              )}
              <h3>{idea.title}</h3>
              <p>{idea.pitch || "No pitch yet"}</p>
              {idea.notes && <small className="notes">{idea.notes}</small>}
              {idea.job_id && (
                <Link
                  className="artifact-link"
                  to="/production/$jobId"
                  params={{ jobId: idea.job_id }}
                >
                  Open video
                  {idea.job_status ? ` · ${label(idea.job_status)}` : ""}
                </Link>
              )}
            </div>
            <div className="model-actions">
              {idea.status === "backlog" && (
                <>
                  <button className="primary" onClick={() => setStarting(idea)}>
                    <Play size={13} /> Start video
                  </button>
                  <button
                    className="secondary"
                    disabled={update.isPending}
                    onClick={() =>
                      update.mutate({ id: idea.id, status: "dropped" })
                    }
                  >
                    <Archive size={13} /> Drop
                  </button>
                </>
              )}
              {idea.status === "dropped" && (
                <button
                  className="secondary"
                  disabled={update.isPending}
                  onClick={() =>
                    update.mutate({ id: idea.id, status: "backlog" })
                  }
                >
                  <RotateCcw size={13} /> Restore
                </button>
              )}
              <button
                className="secondary danger"
                disabled={remove.isPending}
                onClick={() => {
                  if (window.confirm(`Delete idea "${idea.title}"?`))
                    remove.mutate(idea.id);
                }}
              >
                <Trash2 size={13} /> Delete
              </button>
            </div>
          </article>
        ))}
      </div>
      {showForm && (
        <IdeaModal
          seriesId={seriesId}
          themes={themes.data ?? []}
          onClose={() => setShowForm(false)}
        />
      )}
      {starting && (
        <StartIdeaModal
          seriesId={seriesId}
          idea={starting}
          isLocal={isLocal}
          onClose={() => setStarting(null)}
        />
      )}
    </div>
  );
}

function IdeaModal({
  seriesId,
  themes,
  onClose,
}: {
  seriesId: string;
  themes: Theme[];
  onClose: () => void;
}) {
  const client = useQueryClient();
  const [title, setTitle] = useState("");
  const [pitch, setPitch] = useState("");
  const [notes, setNotes] = useState("");
  const [themeId, setThemeId] = useState("");
  const create = useMutation({
    mutationFn: () =>
      api<Idea>(`/series/${seriesId}/ideas`, {
        title,
        pitch,
        notes,
        theme_id: themeId || null,
      }),
    onSuccess: () => {
      void client.invalidateQueries({
        queryKey: ["series", seriesId, "ideas"],
      });
      onClose();
    },
  });
  return (
    <div className="overlay">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="idea-title"
        className="modal"
      >
        <div className="eyebrow">BACKLOG</div>
        <h2 id="idea-title">New idea</h2>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            create.mutate();
          }}
        >
          <label htmlFor="idea-name">Title</label>
          <input
            id="idea-name"
            autoFocus
            required
            maxLength={160}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="How write-ahead logs survive crashes"
          />
          <label htmlFor="idea-pitch">
            Pitch <span>(becomes the brief)</span>
          </label>
          <textarea
            id="idea-pitch"
            rows={3}
            maxLength={3000}
            value={pitch}
            onChange={(e) => setPitch(e.target.value)}
          />
          <label htmlFor="idea-notes">
            Notes <span>(optional)</span>
          </label>
          <textarea
            id="idea-notes"
            rows={2}
            maxLength={1900}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
          <label htmlFor="idea-theme">
            Theme <span>(optional)</span>
          </label>
          <select
            id="idea-theme"
            value={themeId}
            onChange={(e) => setThemeId(e.target.value)}
          >
            <option value="">No theme</option>
            {themes.map((theme) => (
              <option key={theme.id} value={theme.id}>
                {theme.name}
              </option>
            ))}
          </select>
          {create.error && (
            <p role="alert" className="error">
              {create.error.message}
            </p>
          )}
          <div className="actions">
            <button type="button" className="secondary" onClick={onClose}>
              Cancel
            </button>
            <button
              className="primary"
              disabled={!title.trim() || create.isPending}
            >
              {create.isPending ? "Adding…" : "Add idea"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

function StartIdeaModal({
  seriesId,
  idea,
  isLocal,
  onClose,
}: {
  seriesId: string;
  idea: Idea;
  isLocal: boolean;
  onClose: () => void;
}) {
  const client = useQueryClient();
  const navigate = useNavigate();
  const [sourceUrl, setSourceUrl] = useState("");
  const [sourceExcerpt, setSourceExcerpt] = useState("");
  const [librarySourceIds, setLibrarySourceIds] = useState<string[]>([]);
  const needsSource = isLocal && librarySourceIds.length === 0;
  const start = useMutation({
    mutationFn: () =>
      api<Job>(`/series/${seriesId}/ideas/${idea.id}/start`, {
        library_source_ids: librarySourceIds,
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
      void client.invalidateQueries({ queryKey: ["series", seriesId] });
      void client.invalidateQueries({ queryKey: ["jobs"] });
      void navigate({ to: "/production/$jobId", params: { jobId: job.id } });
    },
  });
  return (
    <div className="overlay">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="start-title"
        className="modal"
      >
        <div className="eyebrow">START VIDEO</div>
        <h2 id="start-title">{idea.title}</h2>
        <p>
          Creates a draft video with this idea's pitch as the brief and a
          snapshot of the series bible.
        </p>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            start.mutate();
          }}
        >
          <LibrarySourcePicker
            seriesId={seriesId}
            selected={librarySourceIds}
            onChange={setLibrarySourceIds}
          />
          <label htmlFor="start-source-url">
            Source URL {needsSource ? "(required)" : "(optional)"}
          </label>
          <input
            id="start-source-url"
            type="url"
            autoFocus
            required={needsSource || !!sourceExcerpt}
            value={sourceUrl}
            onChange={(e) => setSourceUrl(e.target.value)}
            placeholder="https://example.com/technical-reference"
          />
          <label htmlFor="start-source-excerpt">Source excerpt</label>
          <textarea
            id="start-source-excerpt"
            rows={5}
            minLength={20}
            maxLength={6000}
            required={needsSource || !!sourceUrl}
            value={sourceExcerpt}
            onChange={(e) => setSourceExcerpt(e.target.value)}
            placeholder="Paste the evidence the research and verification models should use…"
          />
          {start.error && (
            <p role="alert" className="error">
              {start.error.message}
            </p>
          )}
          <div className="actions">
            <button type="button" className="secondary" onClick={onClose}>
              Cancel
            </button>
            <button className="primary" disabled={start.isPending}>
              {start.isPending ? "Starting…" : "Create draft video"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
