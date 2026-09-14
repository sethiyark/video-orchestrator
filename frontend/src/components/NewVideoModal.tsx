import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  api,
  type Job,
  type Series,
  type SeriesAsset,
  type Theme,
} from "../lib/api";
import { LibrarySourcePicker } from "./series/LibrarySourcePicker";

export function NewVideoModal({
  isLocal,
  defaultSeriesId = "",
  onClose,
  onCreated,
}: {
  isLocal: boolean;
  defaultSeriesId?: string;
  onClose: () => void;
  onCreated: (job: Job) => void;
}) {
  const [title, setTitle] = useState("");
  const [brief, setBrief] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [sourceExcerpt, setSourceExcerpt] = useState("");
  const [seriesId, setSeriesId] = useState(defaultSeriesId);
  const [themeId, setThemeId] = useState("");
  const [librarySourceIds, setLibrarySourceIds] = useState<string[]>([]);
  const [captions, setCaptions] = useState(true);
  const [musicAssetId, setMusicAssetId] = useState("");
  const needsSource = isLocal && librarySourceIds.length === 0;
  const assets = useQuery({
    queryKey: ["series", seriesId, "assets", false],
    queryFn: () => api<SeriesAsset[]>(`/series/${seriesId}/assets`),
    enabled: !!seriesId,
  });
  const music = (assets.data ?? []).filter(
    (asset) => asset.status === "active" && ["music", "audio"].includes(asset.kind),
  );
  const series = useQuery({
    queryKey: ["series"],
    queryFn: () => api<Series[]>("/series"),
  });
  const themes = useQuery({
    queryKey: ["series", seriesId, "themes"],
    queryFn: () => api<Theme[]>(`/series/${seriesId}/themes`),
    enabled: !!seriesId,
  });
  const create = useMutation({
    mutationFn: () =>
      api<Job>("/jobs", {
        title,
        brief,
        series_id: seriesId || null,
        theme_id: (seriesId && themeId) || null,
        library_source_ids: seriesId ? librarySourceIds : [],
        render: {
          captions,
          music_asset_id: (seriesId && musicAssetId) || null,
        },
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
    onSuccess: (job) => onCreated(job),
  });
  return (
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
          {(series.data?.length ?? 0) > 0 && (
            <>
              <label htmlFor="series">
                Series <span>(optional)</span>
              </label>
              <select
                id="series"
                value={seriesId}
                onChange={(e) => {
                  setSeriesId(e.target.value);
                  setThemeId("");
                  setLibrarySourceIds([]);
                  setMusicAssetId("");
                }}
              >
                <option value="">Standalone video</option>
                {series.data?.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </>
          )}
          {seriesId && (themes.data?.length ?? 0) > 0 && (
            <>
              <label htmlFor="theme">
                Theme <span>(optional)</span>
              </label>
              <select
                id="theme"
                value={themeId}
                onChange={(e) => setThemeId(e.target.value)}
              >
                <option value="">No theme</option>
                {themes.data?.map((theme) => (
                  <option key={theme.id} value={theme.id}>
                    {theme.name}
                  </option>
                ))}
              </select>
            </>
          )}
          {seriesId && (
            <LibrarySourcePicker
              seriesId={seriesId}
              selected={librarySourceIds}
              onChange={setLibrarySourceIds}
            />
          )}
          <label htmlFor="source-url">
            Source URL {needsSource ? "(required)" : "(optional)"}
          </label>
          <input
            id="source-url"
            type="url"
            required={needsSource || !!sourceExcerpt}
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
            required={needsSource || !!sourceUrl}
            value={sourceExcerpt}
            onChange={(e) => setSourceExcerpt(e.target.value)}
            placeholder="Paste the evidence the research and verification models should use…"
          />
          <p className="muted">
            Local research uses the supplied excerpt. It does not fetch the
            URL. More sources can be supplied through the API.
          </p>
          <div className="field-label">Render options</div>
          <label className="check">
            <input
              type="checkbox"
              checked={captions}
              onChange={(e) => setCaptions(e.target.checked)}
            />
            Word-highlight captions
          </label>
          {seriesId && music.length > 0 && (
            <>
              <label htmlFor="music">
                Music bed <span>(optional, from the series library)</span>
              </label>
              <select
                id="music"
                value={musicAssetId}
                onChange={(e) => setMusicAssetId(e.target.value)}
              >
                <option value="">Series default</option>
                {music.map((asset) => (
                  <option key={asset.id} value={asset.id}>
                    {asset.name || asset.id}
                  </option>
                ))}
              </select>
            </>
          )}
          <p className="muted">
            Starts as a draft. Run the pipeline when you're ready.
          </p>
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
              {create.isPending ? "Creating…" : "Create video"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
