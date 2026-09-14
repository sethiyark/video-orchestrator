import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, apiSend, type BibleVersion } from "../../lib/api";
import { BibleFields, fromDraft, useBibleDraft } from "./BibleFields";

export function BibleTab({ seriesId }: { seriesId: string }) {
  const bible = useQuery({
    queryKey: ["series", seriesId, "bible"],
    queryFn: () => api<BibleVersion>(`/series/${seriesId}/bible`),
  });
  if (bible.isPending) return <div className="empty">Loading bible…</div>;
  if (bible.isError)
    return (
      <div role="alert" className="error">
        {bible.error.message}
      </div>
    );
  // Remount the editor when a new version arrives so the draft resets.
  return (
    <BibleEditor
      key={bible.data.version}
      seriesId={seriesId}
      bible={bible.data}
    />
  );
}

function BibleEditor({
  seriesId,
  bible,
}: {
  seriesId: string;
  bible: BibleVersion;
}) {
  const client = useQueryClient();
  const [draft, setDraft] = useBibleDraft(bible.document);
  const save = useMutation({
    mutationFn: () =>
      apiSend<BibleVersion>(
        `/series/${seriesId}/bible`,
        "PUT",
        fromDraft(draft),
      ),
    onSuccess: (saved) => {
      client.setQueryData(["series", seriesId, "bible"], saved);
      void client.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
  return (
    <form
      className="form-panel"
      onSubmit={(event) => {
        event.preventDefault();
        save.mutate();
      }}
    >
      <div className="form-panel-heading">
        <div>
          <strong>Series bible</strong>
          <small>
            {bible.version === 0
              ? "Not saved yet"
              : `Version ${bible.version}${bible.created_at ? ` · saved ${new Date(bible.created_at).toLocaleString()}` : ""}`}
          </small>
        </div>
        <button className="primary" disabled={save.isPending}>
          {save.isPending ? "Saving…" : "Save new version"}
        </button>
      </div>
      <p className="muted">
        New videos snapshot the bible when they are created. Saving a change
        marks existing videos in this series as needing a restart.
      </p>
      <BibleFields draft={draft} onChange={setDraft} idPrefix="bible" />
      {save.error && (
        <p role="alert" className="error">
          {save.error.message}
        </p>
      )}
    </form>
  );
}
