import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { api, apiDelete, type LibrarySource } from "../../lib/api";

export function SourcesTab({ seriesId }: { seriesId: string }) {
  const client = useQueryClient();
  const sources = useQuery({
    queryKey: ["series", seriesId, "sources"],
    queryFn: () => api<LibrarySource[]>(`/series/${seriesId}/sources`),
  });
  const [key, setKey] = useState("");
  const [title, setTitle] = useState("");
  const [url, setUrl] = useState("");
  const [excerpt, setExcerpt] = useState("");
  const refresh = () =>
    client.invalidateQueries({ queryKey: ["series", seriesId, "sources"] });
  const add = useMutation({
    mutationFn: () =>
      api<LibrarySource>(`/series/${seriesId}/sources`, {
        id: key,
        title,
        url,
        excerpt,
      }),
    onSuccess: () => {
      setKey("");
      setTitle("");
      setUrl("");
      setExcerpt("");
      void refresh();
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => apiDelete(`/series/${seriesId}/sources/${id}`),
    onSuccess: refresh,
  });
  const items = sources.data ?? [];
  return (
    <div>
      <form
        className="form-panel"
        onSubmit={(event) => {
          event.preventDefault();
          add.mutate();
        }}
      >
        <div className="form-panel-heading">
          <div>
            <strong>Add a reusable source</strong>
            <small>
              Videos copy the excerpt when created; editing the library later
              never changes a video's evidence.
            </small>
          </div>
        </div>
        <div className="upload-row">
          <div>
            <label htmlFor="source-key">Source id</label>
            <input
              id="source-key"
              required
              maxLength={80}
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder="rfc1034"
            />
          </div>
          <div className="grow">
            <label htmlFor="source-title">Title</label>
            <input
              id="source-title"
              required
              maxLength={300}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="RFC 1034 — Domain names, concepts and facilities"
            />
          </div>
        </div>
        <label htmlFor="library-source-url">URL</label>
        <input
          id="library-source-url"
          type="url"
          required
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://www.rfc-editor.org/rfc/rfc1034"
        />
        <label htmlFor="library-source-excerpt">Excerpt</label>
        <textarea
          id="library-source-excerpt"
          rows={4}
          required
          minLength={20}
          maxLength={6000}
          value={excerpt}
          onChange={(e) => setExcerpt(e.target.value)}
          placeholder="Paste the exact passage quotes may be drawn from…"
        />
        {add.error && (
          <p role="alert" className="error">
            {add.error.message}
          </p>
        )}
        <div className="actions">
          <button className="primary" disabled={add.isPending}>
            <Plus size={15} /> {add.isPending ? "Adding…" : "Add source"}
          </button>
        </div>
      </form>
      {remove.error && (
        <div role="alert" className="error">
          {remove.error.message}
        </div>
      )}
      <div className="card-list library-sources">
        {items.map((source) => (
          <article key={source.id} className="list-card">
            <div className="min-width">
              <span className="badge key">{source.source_key}</span>
              <h3>{source.title}</h3>
              <p className="source-url">{source.url}</p>
              <small className="notes">{source.excerpt}</small>
            </div>
            <div className="model-actions">
              <button
                className="secondary danger"
                disabled={remove.isPending}
                onClick={() => {
                  if (
                    window.confirm(`Remove "${source.title}" from the library?`)
                  )
                    remove.mutate(source.id);
                }}
              >
                <Trash2 size={13} /> Remove
              </button>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
