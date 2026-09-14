import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { api, apiDelete, apiSend, emptyBible, type Theme } from "../../lib/api";
import { BibleFields, fromDraft, useBibleDraft } from "./BibleFields";

export function ThemesTab({ seriesId }: { seriesId: string }) {
  const client = useQueryClient();
  const themes = useQuery({
    queryKey: ["series", seriesId, "themes"],
    queryFn: () => api<Theme[]>(`/series/${seriesId}/themes`),
  });
  const [editing, setEditing] = useState<Theme | "new" | null>(null);
  const remove = useMutation({
    mutationFn: (id: string) => apiDelete(`/series/${seriesId}/themes/${id}`),
    onSuccess: () =>
      client.invalidateQueries({ queryKey: ["series", seriesId] }),
  });
  const items = themes.data ?? [];
  return (
    <div>
      <div className="tab-toolbar">
        <p className="muted">
          Themes group ideas into arcs. Their guidance is added on top of the
          series bible for videos in that theme.
        </p>
        <button className="primary" onClick={() => setEditing("new")}>
          <Plus size={16} /> New theme
        </button>
      </div>
      {remove.error && (
        <div role="alert" className="error">
          {remove.error.message}
        </div>
      )}
      {themes.isPending && <div className="empty">Loading themes…</div>}
      {!themes.isPending && items.length === 0 && (
        <div className="empty">
          <h2>No themes yet</h2>
          <p>Add one for a recurring arc like “Storage engines”.</p>
        </div>
      )}
      <div className="card-list">
        {items.map((theme) => (
          <article key={theme.id} className="list-card">
            <div>
              <h3>{theme.name}</h3>
              <p>{theme.blurb || "No blurb"}</p>
              <small>{summary(theme)}</small>
            </div>
            <div className="model-actions">
              <button className="secondary" onClick={() => setEditing(theme)}>
                <Pencil size={13} /> Edit
              </button>
              <button
                className="secondary danger"
                disabled={remove.isPending}
                onClick={() => {
                  if (window.confirm(`Delete theme "${theme.name}"?`))
                    remove.mutate(theme.id);
                }}
              >
                <Trash2 size={13} /> Delete
              </button>
            </div>
          </article>
        ))}
      </div>
      {editing && (
        <ThemeModal
          seriesId={seriesId}
          theme={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}

function summary(theme: Theme) {
  const g = theme.guidance;
  const parts = [
    g.voice.style_rules.length && `${g.voice.style_rules.length} style rules`,
    g.glossary.length && `${g.glossary.length} glossary terms`,
    g.visual.image_style && "image style",
  ].filter(Boolean);
  return parts.length ? `Adds ${parts.join(", ")}` : "No extra guidance";
}

function ThemeModal({
  seriesId,
  theme,
  onClose,
}: {
  seriesId: string;
  theme: Theme | null;
  onClose: () => void;
}) {
  const client = useQueryClient();
  const [name, setName] = useState(theme?.name ?? "");
  const [blurb, setBlurb] = useState(theme?.blurb ?? "");
  const [draft, setDraft] = useBibleDraft(theme?.guidance ?? emptyBible());
  const save = useMutation({
    mutationFn: () => {
      const body = { name, blurb, guidance: fromDraft(draft) };
      return theme
        ? apiSend<Theme>(
            `/series/${seriesId}/themes/${theme.id}`,
            "PATCH",
            body,
          )
        : api<Theme>(`/series/${seriesId}/themes`, body);
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["series", seriesId] });
      void client.invalidateQueries({ queryKey: ["jobs"] });
      onClose();
    },
  });
  return (
    <div className="overlay">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="theme-title"
        className="modal modal-wide"
      >
        <div className="eyebrow">THEME</div>
        <h2 id="theme-title">{theme ? "Edit theme" : "New theme"}</h2>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            save.mutate();
          }}
        >
          <label htmlFor="theme-name">Name</label>
          <input
            id="theme-name"
            autoFocus
            required
            maxLength={120}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Storage engines"
          />
          <label htmlFor="theme-blurb">
            Blurb <span>(shared with the writing prompts)</span>
          </label>
          <textarea
            id="theme-blurb"
            rows={2}
            maxLength={1000}
            value={blurb}
            onChange={(e) => setBlurb(e.target.value)}
          />
          <p className="muted">
            Optional guidance below is added to the series bible for videos in
            this theme.
          </p>
          <BibleFields draft={draft} onChange={setDraft} idPrefix="theme" />
          {save.error && (
            <p role="alert" className="error">
              {save.error.message}
            </p>
          )}
          <div className="actions">
            <button type="button" className="secondary" onClick={onClose}>
              Cancel
            </button>
            <button
              className="primary"
              disabled={!name.trim() || save.isPending}
            >
              {save.isPending ? "Saving…" : "Save theme"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
