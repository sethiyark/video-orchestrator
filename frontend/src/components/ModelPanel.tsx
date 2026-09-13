import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";

type ModelStatus = {
  role: string;
  repo_id: string;
  runtime: string;
  device: string;
  cached: boolean;
  runtime_installed: boolean;
  enabled: boolean;
  revision: string | null;
  stages: string[];
};
export function ModelPanel() {
  const query = useQuery({
    queryKey: ["models"],
    queryFn: () => api<{ mode: string; models: ModelStatus[] }>("/models"),
    refetchInterval: 15000,
  });
  return (
    <details className="model-panel">
      <summary>
        Model library <span>Hugging Face · Local inference</span>
      </summary>
      {query.isPending && <p>Checking model cache…</p>}
      {query.isError && (
        <p role="alert">
          Model status is unavailable. Check the backend connection.
        </p>
      )}
      <div className="model-grid">
        {query.data?.models.map((model) => (
          <article key={model.role}>
            <div>
              <strong>{model.role}</strong>
              <span className="badge">
                {!model.enabled
                  ? "optional · disabled"
                  : model.cached && model.runtime_installed
                    ? "prepared"
                    : "setup needed"}
              </span>
            </div>
            <p>{model.repo_id}</p>
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
          </article>
        ))}
      </div>
      <p>
        Prepare weights with <code>python -m app.models.cli download ROLE</code>{" "}
        in the backend environment. Model files alone do not verify hardware or
        runtime compatibility.
      </p>
    </details>
  );
}
