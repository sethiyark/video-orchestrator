import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Check, Play, RotateCcw } from "lucide-react";
import { api, artifactUrl, type Job } from "../lib/api";
import { configChanged, label } from "../lib/format";

export const Route = createFileRoute("/production/$jobId")({
  component: ProductionDetail,
});

function ProductionDetail() {
  const { jobId } = Route.useParams();
  const client = useQueryClient();
  const jobsQuery = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api<Job[]>("/jobs"),
    refetchInterval: 1000,
  });
  const current = jobsQuery.data?.find((job) => job.id === jobId);
  const action = useMutation({
    mutationFn: ({ id, action }: { id: string; action: string }) =>
      api<Job>(`/jobs/${id}/${action}`, {}),
    onSuccess: () => client.invalidateQueries({ queryKey: ["jobs"] }),
  });
  return (
    <div className="app app-focused">
      <main>
        <header>
          <Link className="back-link" to="/">
            <ArrowLeft size={16} /> Back to production
          </Link>
        </header>
        <div className="content">
          {jobsQuery.isPending && (
            <div className="empty">Loading production details…</div>
          )}
          {jobsQuery.isError && (
            <div role="alert" className="error">
              Cannot reach the backend. Start FastAPI on port 8091.{" "}
              <button onClick={() => void jobsQuery.refetch()}>Retry</button>
            </div>
          )}
          {!jobsQuery.isPending && !jobsQuery.isError && !current && (
            <div className="empty">
              <h2>Video not found</h2>
              <p>It may have been removed. Go back and pick another one.</p>
            </div>
          )}
          {current && (
            <section className="detail detail-page">
              <div className="detail-heading">
                <div className="min-width">
                  <div className="eyebrow">PRODUCTION DETAILS</div>
                  <h2>{current.title}</h2>
                </div>
                <div className="actions">
                  {["draft", "failed"].includes(current.status) && (
                    <button
                      className={
                        configChanged(current, action.error?.message)
                          ? "secondary"
                          : "primary"
                      }
                      disabled={action.isPending}
                      onClick={() =>
                        action.mutate({ id: current.id, action: "run" })
                      }
                    >
                      <Play size={15} />
                      {current.status === "failed"
                        ? "Retry pipeline"
                        : "Run pipeline"}
                    </button>
                  )}
                  {[
                    "draft",
                    "failed",
                    "awaiting_approval",
                    "completed",
                  ].includes(current.status) && (
                    <button
                      className={
                        configChanged(current, action.error?.message)
                          ? "primary"
                          : "secondary"
                      }
                      disabled={action.isPending}
                      onClick={() =>
                        action.mutate({ id: current.id, action: "restart" })
                      }
                    >
                      <RotateCcw size={15} /> Restart pipeline
                    </button>
                  )}
                  {current.status === "awaiting_approval" && (
                    <button
                      className="primary"
                      disabled={action.isPending}
                      onClick={() =>
                        action.mutate({ id: current.id, action: "approve" })
                      }
                    >
                      <Check size={16} /> Approve mock upload
                    </button>
                  )}
                </div>
              </div>
              {current.status === "awaiting_approval" && (
                <div className="review-note">
                  Review the outputs below before approving. All outputs are
                  placeholders; no playable video has been generated.
                </div>
              )}
              {(current.error || action.error) && (
                <p role="alert" className="error">
                  {action.error?.message || current.error}
                </p>
              )}
              <div className="stages">
                {current.stages.map((stage, index) => (
                  <details key={stage.name}>
                    <summary>
                      <span className={`step ${stage.status}`}>
                        {stage.status === "completed" ? (
                          <Check size={14} />
                        ) : (
                          index + 1
                        )}
                      </span>
                      <strong>{label(stage.name)}</strong>
                      <span className={`badge ${stage.status}`}>
                        {stage.status}
                      </span>
                    </summary>
                    {stage.output ? (
                      <div>
                        <pre>{JSON.stringify(stage.output, null, 2)}</pre>
                        {typeof stage.output.artifact === "object" &&
                          stage.output.artifact &&
                          "id" in stage.output.artifact && (
                            <a
                              className="artifact-link"
                              href={artifactUrl(
                                current.id,
                                String(stage.output.artifact.id),
                              )}
                            >
                              Download stage JSON
                            </a>
                          )}
                        {typeof stage.output.audio === "object" &&
                          stage.output.audio &&
                          "id" in stage.output.audio && (
                            <a
                              className="artifact-link"
                              href={artifactUrl(
                                current.id,
                                String(stage.output.audio.id),
                              )}
                            >
                              Download narration WAV
                            </a>
                          )}
                      </div>
                    ) : (
                      <p className="muted">
                        Output will appear when this stage completes.
                      </p>
                    )}
                  </details>
                ))}
              </div>
            </section>
          )}
        </div>
      </main>
    </div>
  );
}
