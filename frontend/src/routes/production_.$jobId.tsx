import { useState } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  BookOpen,
  BookUp,
  Check,
  Play,
  RotateCcw,
  Trash2,
} from "lucide-react";
import {
  api,
  apiDelete,
  artifactUrl,
  type AssetKind,
  type Job,
  type SeriesAsset,
} from "../lib/api";
import { label, needsRestart } from "../lib/format";

export const Route = createFileRoute("/production_/$jobId")({
  component: ProductionDetail,
});

function ProductionDetail() {
  const { jobId } = Route.useParams();
  const client = useQueryClient();
  const navigate = useNavigate();
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
  const [promoted, setPromoted] = useState("");
  const promote = useMutation({
    mutationFn: ({
      artifactId,
      name,
      kind,
    }: {
      artifactId: string;
      name: string;
      kind: AssetKind;
    }) =>
      api<SeriesAsset>(`/jobs/${jobId}/artifacts/${artifactId}/promote`, {
        name,
        kind,
      }),
    onSuccess: (asset) => {
      setPromoted(
        asset.duplicate
          ? `Already in the series library as “${asset.name}”.`
          : `Added “${asset.name}” to the series library.`,
      );
      void client.invalidateQueries({ queryKey: ["series"] });
    },
  });
  const promoteButton = (artifactId: string, fallback: string, kind: AssetKind) =>
    current?.series_id ? (
      <button
        type="button"
        className="secondary promote"
        disabled={promote.isPending}
        onClick={() => {
          const name = window.prompt("Name in the series library", fallback);
          if (name?.trim())
            promote.mutate({ artifactId, name: name.trim(), kind });
        }}
      >
        <BookUp size={13} /> Promote to series
      </button>
    ) : null;
  const deleteJob = useMutation({
    mutationFn: (id: string) => apiDelete(`/jobs/${id}`),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["jobs"] });
      void navigate({ to: "/production" });
    },
  });
  return (
    <div className="app app-focused">
      <main>
        <header>
          <Link className="back-link" to="/production">
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
                  {current.series_context && (
                    <Link
                      className="series-badge"
                      to="/series/$seriesId"
                      params={{ seriesId: current.series_context.series.id }}
                    >
                      <BookOpen size={13} /> {current.series_context.series.name}
                      {current.series_context.theme &&
                        ` · ${current.series_context.theme.name}`}
                      {` · bible v${current.series_context.bible_version}`}
                    </Link>
                  )}
                </div>
                <div className="actions">
                  {["draft", "failed"].includes(current.status) && (
                    <button
                      className={
                        needsRestart(current, action.error?.message)
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
                        needsRestart(current, action.error?.message)
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
                  <button
                    className="secondary danger"
                    disabled={deleteJob.isPending}
                    onClick={() => {
                      if (
                        window.confirm(
                          `Delete "${current.title}"? This cannot be undone.`,
                        )
                      )
                        deleteJob.mutate(current.id);
                    }}
                  >
                    <Trash2 size={15} /> Delete pipeline
                  </button>
                </div>
              </div>
              {current.series_stale && (
                <div className="review-note">
                  <AlertTriangle size={15} /> The series bible or theme changed
                  since this video was created. Restart the pipeline to use the
                  current guidance.
                </div>
              )}
              {current.status === "awaiting_approval" && (
                <div className="review-note">
                  Review the outputs below before approving. All outputs are
                  placeholders; no playable video has been generated.
                </div>
              )}
              {(current.error ||
                action.error ||
                deleteJob.error ||
                promote.error) && (
                <p role="alert" className="error">
                  {action.error?.message ||
                    deleteJob.error?.message ||
                    promote.error?.message ||
                    current.error}
                </p>
              )}
              {promoted && <p className="review-note">{promoted}</p>}
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
                        {typeof stage.output.audio === "object" &&
                          stage.output.audio &&
                          "id" in stage.output.audio &&
                          promoteButton(
                            String(stage.output.audio.id),
                            `${current.title} narration`,
                            "audio",
                          )}
                        {Array.isArray(stage.output.images) &&
                          stage.output.images.map((image, imageIndex) => {
                            const id = (image as { artifact?: { id?: string } })
                              .artifact?.id;
                            return id ? (
                              <span key={id} className="artifact-row">
                                <a
                                  className="artifact-link"
                                  href={artifactUrl(current.id, id)}
                                >
                                  Download image {imageIndex + 1}
                                </a>
                                {promoteButton(
                                  id,
                                  `${current.title} image ${imageIndex + 1}`,
                                  "image",
                                )}
                              </span>
                            ) : null;
                          })}
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
