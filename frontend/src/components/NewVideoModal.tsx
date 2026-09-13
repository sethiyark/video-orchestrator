import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api, type Job } from "../lib/api";

export function NewVideoModal({
  isLocal,
  onClose,
  onCreated,
}: {
  isLocal: boolean;
  onClose: () => void;
  onCreated: (job: Job) => void;
}) {
  const [title, setTitle] = useState("");
  const [brief, setBrief] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [sourceExcerpt, setSourceExcerpt] = useState("");
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
