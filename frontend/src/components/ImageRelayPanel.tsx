import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Clipboard, Images, Upload } from "lucide-react";
import {
  artifactUrl,
  skipManualImages,
  uploadManualImage,
  type ManualStageOutput,
} from "../lib/api";

/**
 * The assets stage parked on the image relay: every image the video still
 * needs, with its prompt, an upload control per id, and a skip for scenes.
 * Nothing here talks to Claude/Gemini — the user does, in their own tab.
 */
export function ImageRelayPanel({
  jobId,
  manual,
}: {
  jobId: string;
  manual: NonNullable<ManualStageOutput["manual"]>;
}) {
  const client = useQueryClient();
  const [error, setError] = useState("");
  const expected = manual.expected_images ?? [];
  const uploaded = manual.images ?? {};
  const skipped = new Set(manual.skipped ?? []);
  const missing = new Set(manual.missing ?? expected.map((item) => item.id));
  const upload = useMutation({
    mutationFn: ({ id, file }: { id: string; file: File }) =>
      uploadManualImage(jobId, id, file),
    onSuccess: () => {
      setError("");
      void client.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: (err: Error) => setError(err.message),
  });
  const skip = useMutation({
    mutationFn: (ids: string[]) => skipManualImages(jobId, ids),
    onSuccess: () => {
      setError("");
      void client.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: (err: Error) => setError(err.message),
  });
  const missingScenes = expected.filter(
    (item) => item.kind === "scene" && missing.has(item.id),
  );
  return (
    <div className="image-relay">
      <p className="muted">
        <Images size={14} /> {missing.size} of {expected.length} images still
        needed. Copy the prompt list into Claude Pro or Gemini Pro, generate
        each 16:9 image, then upload it under its id. Chapter heroes are
        required; scene images can fall back to their chapter hero.
      </p>
      <div className="relay-actions">
        <button
          type="button"
          className="secondary"
          onClick={() => {
            navigator.clipboard.writeText(manual.prompt ?? "").catch(() => {
              // Clipboard denied; the list below stays selectable.
            });
          }}
        >
          <Clipboard size={14} /> Copy prompt list
        </button>
        {missingScenes.length > 0 && (
          <button
            type="button"
            className="secondary"
            disabled={skip.isPending}
            onClick={() => skip.mutate([])}
          >
            Use chapter heroes for {missingScenes.length} remaining scene
            {missingScenes.length === 1 ? "" : "s"}
          </button>
        )}
      </div>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <ul className="relay-list">
        {expected.map((item) => {
          const record = uploaded[item.id];
          const done = !!record || skipped.has(item.id);
          return (
            <li key={item.id} className={`relay-item${done ? " done" : ""}`}>
              <div>
                <code>{item.id}</code>{" "}
                <span className="muted">
                  {item.kind === "hero" ? "chapter hero" : "scene image"}
                  {skipped.has(item.id) && " · using chapter hero"}
                </span>
              </div>
              {record ? (
                <img src={artifactUrl(jobId, record.artifact.id)} alt="" />
              ) : (
                <label className="secondary">
                  <Upload size={13} /> Upload
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    hidden
                    disabled={upload.isPending}
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) upload.mutate({ id: item.id, file });
                      event.target.value = "";
                    }}
                  />
                </label>
              )}
              <div className="prompt">{item.prompt}</div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
