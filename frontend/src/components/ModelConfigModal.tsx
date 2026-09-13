import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api, type ModelDevice, type ModelStatus } from "../lib/api";

type Props = { model: ModelStatus; onClose: () => void; onSaved: () => void };
type Draft = {
  repo_id: string;
  revision: string;
  filename: string;
  files: string;
  device: ModelDevice;
  gpu_layers: string;
  context_size: string;
  max_tokens: string;
  voice: string;
  speed: string;
  steps: string;
};
const TTS = new Set(["kokoro", "qwen_tts"]);
const IMAGES = new Set(["diffusers", "diffusers_gguf"]);

function toDraft(model: ModelStatus): Draft {
  const spec = model.spec;
  return {
    repo_id: spec.repo_id,
    revision: spec.revision,
    filename: spec.filename ?? "",
    files: spec.files.join("\n"),
    device: spec.device,
    gpu_layers: String(spec.gpu_layers),
    context_size: String(spec.context_size),
    max_tokens: String(spec.max_tokens),
    voice: spec.voice,
    speed: String(spec.speed),
    steps: String(spec.steps),
  };
}

/** Only fields that differ from the current spec are sent; the rest stay untouched. */
function diff(model: ModelStatus, draft: Draft): Record<string, unknown> {
  const spec = model.spec;
  const out: Record<string, unknown> = {};
  if (draft.repo_id.trim() !== spec.repo_id) out.repo_id = draft.repo_id.trim();
  if (draft.revision.trim() !== spec.revision)
    out.revision = draft.revision.trim();
  const filename = draft.filename.trim() || null;
  if (filename !== spec.filename) out.filename = filename;
  const files = draft.files
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  if (files.join("\n") !== spec.files.join("\n")) out.files = files;
  if (draft.device !== spec.device) out.device = draft.device;
  const numbers: Array<[keyof Draft, keyof typeof spec]> = [
    ["gpu_layers", "gpu_layers"],
    ["context_size", "context_size"],
    ["max_tokens", "max_tokens"],
    ["speed", "speed"],
    ["steps", "steps"],
  ];
  for (const [key, field] of numbers) {
    const value = Number(draft[key]);
    if (draft[key] !== "" && value !== spec[field]) out[field] = value;
  }
  if (draft.voice.trim() !== spec.voice) out.voice = draft.voice.trim();
  return out;
}

export function ModelConfigModal({ model, onClose, onSaved }: Props) {
  const [draft, setDraft] = useState<Draft>(() => toDraft(model));
  const set = (key: keyof Draft) => (value: string) =>
    setDraft((current) => ({ ...current, [key]: value }));
  const changes = diff(model, draft);
  const save = useMutation({
    mutationFn: () => api(`/models/${model.role}/config`, changes),
    onSuccess: onSaved,
  });
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  const field = (
    id: keyof Draft,
    label: string,
    props: React.InputHTMLAttributes<HTMLInputElement> = {},
  ) => (
    <>
      <label htmlFor={`model-${id}`}>{label}</label>
      <input
        id={`model-${id}`}
        value={draft[id]}
        onChange={(e) => set(id)(e.target.value)}
        {...props}
      />
    </>
  );
  return (
    <div className="overlay">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="model-config-title"
        className="modal"
      >
        <div className="eyebrow">MODEL LIBRARY</div>
        <h2 id="model-config-title">Configure {model.role}</h2>
        <p>
          {model.runtime} · {model.stages.join(" · ")}. Runtime and stage
          routing come from the hardware profile and cannot be changed here.
        </p>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            save.mutate();
          }}
        >
          {field("repo_id", "Hugging Face repo", {
            required: true,
            autoFocus: true,
            placeholder: "owner/model",
          })}
          {field("revision", "Revision", {
            required: true,
            placeholder: "main or a commit sha",
          })}
          {field("filename", "Weight filename", {
            placeholder: "Leave blank when the runtime loads a directory",
          })}
          <label htmlFor="model-files">
            Files to download <span>(one glob per line)</span>
          </label>
          <textarea
            id="model-files"
            className="mono"
            rows={3}
            required
            value={draft.files}
            onChange={(e) => set("files")(e.target.value)}
          />
          <label htmlFor="model-device">Device</label>
          <select
            id="model-device"
            value={draft.device}
            onChange={(e) => set("device")(e.target.value)}
          >
            <option value="cpu">cpu</option>
            <option value="metal">metal</option>
            <option value="cuda">cuda</option>
          </select>
          {model.runtime === "llama_cpp" && (
            <>
              {field("gpu_layers", "GPU layers", {
                type: "number",
                min: -1,
                step: 1,
              })}
              {field("context_size", "Context size", {
                type: "number",
                min: 512,
                max: 32768,
                step: 1,
              })}
              {field("max_tokens", "Max tokens", {
                type: "number",
                min: 64,
                max: 8192,
                step: 1,
              })}
            </>
          )}
          {TTS.has(model.runtime) && (
            <>
              {field("voice", "Voice")}
              {field("speed", "Speed", {
                type: "number",
                min: 0.5,
                max: 2,
                step: 0.05,
              })}
            </>
          )}
          {IMAGES.has(model.runtime) &&
            field("steps", "Diffusion steps", {
              type: "number",
              min: 1,
              max: 50,
              step: 1,
            })}
          <p className="muted">
            Saved to the local overlay file. Weights for a changed repo or
            revision must be downloaded again, and queued local jobs will need a
            restart.
          </p>
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
              type="submit"
              className="primary"
              disabled={save.isPending || Object.keys(changes).length === 0}
            >
              {save.isPending ? "Saving…" : "Save override"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
