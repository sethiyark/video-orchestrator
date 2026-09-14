import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type ModelStatus, type ModelsResponse } from "../lib/api";
import { ModelConfigModal } from "./ModelConfigModal";

function badge(model: ModelStatus): { text: string; className: string } {
  const { download, install } = model.setup;
  if (download.state === "running")
    return { text: "downloading", className: "running" };
  if (install.state === "running")
    return { text: "installing", className: "running" };
  if (download.state === "failed" || install.state === "failed")
    return { text: "setup failed", className: "failed" };
  if (!model.enabled) return { text: "optional · disabled", className: "" };
  if (model.cached && model.runtime_installed)
    return { text: "prepared", className: "completed" };
  return { text: "setup needed", className: "" };
}

export function ModelPanel() {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["models"],
    queryFn: () => api<ModelsResponse>("/models"),
    refetchInterval: (state) =>
      state.state.data?.setup_running ? 2000 : 15000,
  });
  const [configuring, setConfiguring] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const refresh = () => client.invalidateQueries({ queryKey: ["models"] });
  const action = useMutation({
    mutationFn: ({ role, path }: { role: string; path: string }) =>
      api(`/models/${role}/${path}`, {}),
    onMutate: () => setError(null),
    onSuccess: refresh,
    onError: (err: Error) => setError(err.message),
  });
  const busy = (model: ModelStatus) =>
    model.setup.download.state === "running" ||
    model.setup.install.state === "running";
  const editing = query.data?.models.find((m) => m.role === configuring);
  return (
    <section className="model-panel">
      <div className="model-panel-heading">
        Model library <span>Hugging Face · Local inference</span>
      </div>
      {query.isPending && <p>Checking model cache…</p>}
      {query.isError && (
        <p role="alert">
          Model status is unavailable. Check the backend connection.
        </p>
      )}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <div className="model-grid">
        {query.data?.models.map((model) => {
          const status = badge(model);
          const setupError =
            model.setup.download.error ?? model.setup.install.error;
          return (
            <article key={model.role}>
              <div>
                <strong>{model.role}</strong>
                <span className={`badge ${status.className}`}>
                  {status.text}
                </span>
              </div>
              <p>
                {model.repo_id}
                {model.overridden && (
                  <small className="override"> · overridden</small>
                )}
              </p>
              <small>
                {model.runtime} · {model.device.toUpperCase()}
              </small>
              <p>{model.stages.join(" · ")}</p>
              <small>
                Weights: {model.cached ? "cached" : "not downloaded"} · Runtime:{" "}
                {model.runtime_installed ? "installed" : "not installed"}
              </small>
              {model.revision && (
                <small className="revision">
                  Revision: {model.revision.slice(0, 12)}
                </small>
              )}
              {setupError && (
                <small className="setup-error" role="alert">
                  {setupError}
                </small>
              )}
              <div className="model-actions">
                {!model.cached && (
                  <button
                    type="button"
                    className="secondary"
                    disabled={!model.enabled || busy(model) || action.isPending}
                    onClick={() =>
                      action.mutate({ role: model.role, path: "download" })
                    }
                  >
                    {model.setup.download.state === "running"
                      ? "Downloading…"
                      : "Download weights"}
                  </button>
                )}
                {!model.runtime_installed && (
                  <button
                    type="button"
                    className="secondary"
                    title={model.install_command}
                    disabled={busy(model) || action.isPending}
                    onClick={() =>
                      action.mutate({
                        role: model.role,
                        path: "install-runtime",
                      })
                    }
                  >
                    {model.setup.install.state === "running"
                      ? "Installing…"
                      : `Install runtime (${model.extra})`}
                  </button>
                )}
                <button
                  type="button"
                  className="secondary"
                  disabled={model.setup.download.state === "running"}
                  onClick={() => setConfiguring(model.role)}
                >
                  Configure
                </button>
                {model.overridden && (
                  <button
                    type="button"
                    className="secondary"
                    disabled={model.setup.download.state === "running"}
                    onClick={() => {
                      if (
                        window.confirm(
                          `Reset ${model.role} to the profile default?`,
                        )
                      )
                        action.mutate({
                          role: model.role,
                          path: "config/reset",
                        });
                    }}
                  >
                    Reset
                  </button>
                )}
              </div>
              {model.setup.install.state === "running" &&
                model.setup.install.log.length > 0 && (
                  <small className="setup-log">
                    {
                      model.setup.install.log[
                        model.setup.install.log.length - 1
                      ]
                    }
                  </small>
                )}
            </article>
          );
        })}
      </div>
      <p>
        Download weights and install runtimes here, or run{" "}
        <code>python -m app.models.cli download ROLE</code> in the backend
        environment. Runtime installs run <code>uv sync --extra …</code> in{" "}
        <code>backend/</code> and can take several minutes. Model files alone do
        not verify hardware compatibility.
      </p>
      {editing && (
        <ModelConfigModal
          model={editing}
          onClose={() => setConfiguring(null)}
          onSaved={() => {
            setConfiguring(null);
            refresh();
          }}
        />
      )}
    </section>
  );
}
