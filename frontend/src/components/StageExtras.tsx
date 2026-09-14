import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  api,
  artifactUrl,
  updateRenderOptions,
  type Chapter,
  type Job,
  type SeriesAsset,
  type StoryboardScene,
} from "../lib/api";

/** Chapters and scenes of a completed storyboard stage. */
export function StoryboardSummary({ output }: { output: Record<string, unknown> }) {
  const scenes = (output.scenes as StoryboardScene[] | undefined) ?? [];
  const chapters = (output.chapters as Chapter[] | undefined) ?? [];
  if (!scenes.length) return null;
  const chapterOf = (sceneId: string) =>
    chapters.find(
      (chapter) => sceneId >= chapter.first_scene && sceneId <= chapter.last_scene,
    );
  return (
    <>
      {chapters.length > 0 && (
        <div className="chapters">
          {chapters.map((chapter, index) => (
            <div key={chapter.chapter_id} className="chapter-card">
              <strong>
                Chapter {index + 1}: {chapter.title}
              </strong>
              <small>
                {chapter.tagline || "—"} · {chapter.first_scene} → {chapter.last_scene}
              </small>
            </div>
          ))}
        </div>
      )}
      <ul className="scene-list">
        {scenes.map((scene) => (
          <li key={scene.scene_id}>
            <code>{scene.scene_id}</code>{" "}
            <span className="component">{scene.component}</span>
            {scene.props.title ? ` ${scene.props.title}` : ""}
            {chapters.length > 0 && chapterOf(scene.scene_id)?.first_scene === scene.scene_id && (
              <em className="muted"> · opens {chapterOf(scene.scene_id)?.title}</em>
            )}
            {scene.image_prompt && (
              <div className="muted">image: {scene.image_prompt}</div>
            )}
          </li>
        ))}
      </ul>
    </>
  );
}

type ImageRecord = {
  id?: string;
  scene_id?: string;
  kind?: string;
  cache?: string;
  fallback?: string;
  artifact?: { id: string };
};

/** Thumbnails of every generated, relayed, or cached image. */
export function ImageThumbs({ jobId, images }: { jobId: string; images: ImageRecord[] }) {
  const shown = images.filter((image) => image.artifact?.id);
  const fallbacks = images.filter((image) => image.fallback);
  if (!shown.length && !fallbacks.length) return null;
  return (
    <>
      <div className="thumbs">
        {shown.map((image) => (
          <figure key={image.artifact!.id + (image.id ?? image.scene_id ?? "")}>
            <img src={artifactUrl(jobId, image.artifact!.id)} alt="" />
            <figcaption>
              {image.id ?? image.scene_id}
              {image.cache ? ` · ${image.cache}` : ""}
            </figcaption>
          </figure>
        ))}
      </div>
      {fallbacks.length > 0 && (
        <p className="muted">
          {fallbacks.length} scene{fallbacks.length === 1 ? "" : "s"} reuse their
          chapter hero plate.
        </p>
      )}
    </>
  );
}

/** Captions and music bed, editable until the render stage has run. */
export function RenderOptionsPanel({ job }: { job: Job }) {
  const client = useQueryClient();
  const renderStage = job.stages.find((stage) => stage.name === "render");
  const locked =
    ["queued", "running"].includes(job.status) || renderStage?.status === "completed";
  const options = job.render ?? { captions: true, music_asset_id: null };
  const assets = useQuery({
    queryKey: ["series", job.series_id, "assets", false],
    queryFn: () => api<SeriesAsset[]>(`/series/${job.series_id}/assets`),
    enabled: !!job.series_id,
  });
  const music = (assets.data ?? []).filter(
    (asset) => asset.status === "active" && ["music", "audio"].includes(asset.kind),
  );
  const save = useMutation({
    mutationFn: (next: typeof options) => updateRenderOptions(job.id, next),
    onSuccess: () => client.invalidateQueries({ queryKey: ["jobs"] }),
  });
  return (
    <div className="render-options">
      <label className="check">
        <input
          type="checkbox"
          checked={options.captions}
          disabled={locked || save.isPending}
          onChange={(e) => save.mutate({ ...options, captions: e.target.checked })}
        />
        Word-highlight captions
      </label>
      {job.series_id && (
        <label>
          Music bed{" "}
          <select
            value={options.music_asset_id ?? ""}
            disabled={locked || save.isPending}
            onChange={(e) =>
              save.mutate({ ...options, music_asset_id: e.target.value || null })
            }
          >
            <option value="">Series default</option>
            {music.map((asset) => (
              <option key={asset.id} value={asset.id}>
                {asset.name || asset.id}
              </option>
            ))}
          </select>
        </label>
      )}
      {locked && <span className="muted">Locked once rendering starts.</span>}
      {save.error && (
        <span role="alert" className="error">
          {save.error.message}
        </span>
      )}
    </div>
  );
}
