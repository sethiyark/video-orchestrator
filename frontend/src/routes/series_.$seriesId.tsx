import { useState } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowUpRight, Plus, Trash2 } from "lucide-react";
import { api, apiDelete, type Series } from "../lib/api";
import { label } from "../lib/format";
import { AssetsTab } from "../components/series/AssetsTab";
import { BibleTab } from "../components/series/BibleTab";
import { IdeasTab } from "../components/series/IdeasTab";
import { SeriesChrome, useWorkspace } from "../components/series/SeriesChrome";
import { SourcesTab } from "../components/series/SourcesTab";
import { ThemesTab } from "../components/series/ThemesTab";
import { NewVideoModal } from "../components/NewVideoModal";

export const Route = createFileRoute("/series_/$seriesId")({
  component: SeriesDetail,
});

const TABS = [
  "bible",
  "themes",
  "ideas",
  "assets",
  "sources",
  "videos",
] as const;
type Tab = (typeof TABS)[number];

function SeriesDetail() {
  const { seriesId } = Route.useParams();
  const navigate = useNavigate();
  const client = useQueryClient();
  const { jobs, isLocal } = useWorkspace();
  const series = useQuery({
    queryKey: ["series", seriesId],
    queryFn: () => api<Series>(`/series/${seriesId}`),
  });
  const [tab, setTab] = useState<Tab>("bible");
  const [showForm, setShowForm] = useState(false);
  const remove = useMutation({
    mutationFn: () => apiDelete(`/series/${seriesId}`),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["series"] });
      void navigate({ to: "/series" });
    },
  });
  const videos = jobs.data?.filter((job) => job.series_id === seriesId) ?? [];
  const stale = videos.filter((job) => job.series_stale).length;
  return (
    <SeriesChrome
      crumb={
        <>
          <Link to="/series" className="crumb-link">
            Series
          </Link>{" "}
          <span className="slash">/</span> {series.data?.name ?? "…"}
        </>
      }
    >
      {series.isPending && <div className="empty">Loading series…</div>}
      {series.isError && (
        <div className="empty">
          <h2>Series not found</h2>
          <p>{series.error.message}</p>
        </div>
      )}
      {series.data && (
        <>
          <div className="detail-heading">
            <div className="min-width">
              <div className="eyebrow">SERIES · /{series.data.slug}</div>
              <h1>{series.data.name}</h1>
              {series.data.description && <p>{series.data.description}</p>}
            </div>
            <div className="actions">
              <button className="primary" onClick={() => setShowForm(true)}>
                <Plus size={15} /> New video
              </button>
              <button
                className="secondary danger"
                disabled={remove.isPending}
                onClick={() => {
                  if (
                    window.confirm(
                      `Delete series "${series.data.name}" with its bible, themes, and ideas?`,
                    )
                  )
                    remove.mutate();
                }}
              >
                <Trash2 size={15} /> Delete series
              </button>
            </div>
          </div>
          {remove.error && (
            <p role="alert" className="error">
              {remove.error.message}
            </p>
          )}
          <div className="tabs" role="tablist">
            {TABS.map((name) => (
              <button
                key={name}
                role="tab"
                aria-selected={tab === name}
                className={tab === name ? "tab active" : "tab"}
                onClick={() => setTab(name)}
              >
                {name}
                {name === "videos" && (
                  <span className="count">{videos.length}</span>
                )}
              </button>
            ))}
          </div>
          {tab === "bible" && <BibleTab seriesId={seriesId} />}
          {tab === "themes" && <ThemesTab seriesId={seriesId} />}
          {tab === "ideas" && (
            <IdeasTab seriesId={seriesId} isLocal={isLocal} />
          )}
          {tab === "assets" && <AssetsTab seriesId={seriesId} />}
          {tab === "sources" && <SourcesTab seriesId={seriesId} />}
          {tab === "videos" && (
            <div>
              {stale > 0 && (
                <div className="review-note">
                  <AlertTriangle size={15} /> {stale} video
                  {stale === 1 ? " uses" : "s use"} an older bible or theme.
                  Restart them to pick up the current guidance.
                </div>
              )}
              {videos.length === 0 && (
                <div className="empty">
                  <h2>No videos in this series yet</h2>
                  <p>Start one from an idea or with “New video”.</p>
                </div>
              )}
              <div className="card-list">
                {videos.map((job) => (
                  <Link
                    key={job.id}
                    to="/production/$jobId"
                    params={{ jobId: job.id }}
                    className="list-card list-card-link"
                  >
                    <div className="min-width">
                      <span className={`badge ${job.status}`}>
                        {label(job.status)}
                      </span>
                      {job.series_context?.theme && (
                        <span className="badge theme">
                          {job.series_context.theme.name}
                        </span>
                      )}
                      {job.series_stale && (
                        <span className="badge failed">bible changed</span>
                      )}
                      <h3>{job.title}</h3>
                      <small>
                        Bible v{job.series_context?.bible_version ?? 0} ·{" "}
                        {
                          job.stages.filter((s) => s.status === "completed")
                            .length
                        }{" "}
                        / {job.stages.length} stages
                      </small>
                    </div>
                    <ArrowUpRight size={16} />
                  </Link>
                ))}
              </div>
            </div>
          )}
        </>
      )}
      {showForm && (
        <NewVideoModal
          isLocal={isLocal}
          defaultSeriesId={seriesId}
          onClose={() => setShowForm(false)}
          onCreated={(job) => {
            setShowForm(false);
            void navigate({
              to: "/production/$jobId",
              params: { jobId: job.id },
            });
          }}
        />
      )}
    </SeriesChrome>
  );
}
