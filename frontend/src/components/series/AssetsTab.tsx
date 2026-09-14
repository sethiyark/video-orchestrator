import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, RotateCcw, Upload } from "lucide-react";
import {
  api,
  apiSend,
  apiUpload,
  assetUrl,
  type AssetKind,
  type SeriesAsset,
} from "../../lib/api";

const KINDS: AssetKind[] = [
  "logo",
  "image",
  "audio",
  "music",
  "video",
  "other",
];
const ACCEPT =
  "image/png,image/jpeg,image/webp,audio/wav,audio/x-wav,audio/mpeg,video/mp4";

const guessKind = (file: File): AssetKind =>
  file.type.startsWith("audio/")
    ? "audio"
    : file.type.startsWith("video/")
      ? "video"
      : "image";

const size = (bytes: number) =>
  bytes > 1024 * 1024
    ? `${(bytes / 1024 / 1024).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`;

export function AssetsTab({ seriesId }: { seriesId: string }) {
  const client = useQueryClient();
  const [showArchived, setShowArchived] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [kind, setKind] = useState<AssetKind>("image");
  const [notice, setNotice] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const assets = useQuery({
    queryKey: ["series", seriesId, "assets", showArchived],
    queryFn: () =>
      api<SeriesAsset[]>(
        `/series/${seriesId}/assets?include_archived=${showArchived}`,
      ),
  });
  const refresh = () =>
    client.invalidateQueries({ queryKey: ["series", seriesId, "assets"] });
  const upload = useMutation({
    mutationFn: () =>
      apiUpload<SeriesAsset>(
        `/series/${seriesId}/assets?name=${encodeURIComponent(name)}&kind=${kind}`,
        file as File,
      ),
    onSuccess: (asset) => {
      setNotice(
        asset.duplicate
          ? `This file is already in the library as “${asset.name}”${asset.status === "archived" ? " (archived)" : ""}.`
          : "",
      );
      setFile(null);
      setName("");
      if (input.current) input.current.value = "";
      void refresh();
    },
  });
  const update = useMutation({
    mutationFn: ({
      id,
      status,
    }: {
      id: string;
      status: SeriesAsset["status"];
    }) =>
      apiSend<SeriesAsset>(`/series/${seriesId}/assets/${id}`, "PATCH", {
        status,
      }),
    onSuccess: refresh,
  });
  const items = assets.data ?? [];
  return (
    <div>
      <form
        className="form-panel upload-panel"
        onSubmit={(event) => {
          event.preventDefault();
          upload.mutate();
        }}
      >
        <div className="upload-row">
          <div>
            <label htmlFor="asset-file">File</label>
            <input
              id="asset-file"
              ref={input}
              type="file"
              accept={ACCEPT}
              required
              onChange={(e) => {
                const picked = e.target.files?.[0] ?? null;
                setFile(picked);
                if (picked) {
                  setKind(guessKind(picked));
                  if (!name) setName(picked.name.replace(/\.[^.]+$/, ""));
                }
              }}
            />
          </div>
          <div>
            <label htmlFor="asset-name">Name</label>
            <input
              id="asset-name"
              required
              maxLength={200}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Channel logo"
            />
          </div>
          <div>
            <label htmlFor="asset-kind">Kind</label>
            <select
              id="asset-kind"
              value={kind}
              onChange={(e) => setKind(e.target.value as AssetKind)}
            >
              {KINDS.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </div>
          <button
            className="primary"
            disabled={!file || !name.trim() || upload.isPending}
          >
            <Upload size={15} /> {upload.isPending ? "Uploading…" : "Upload"}
          </button>
        </div>
        <p className="muted">
          PNG, JPEG, WebP, WAV, MP3 or MP4. Identical files are stored once.
          Logos and images can be placed in storyboards.
        </p>
        {notice && <p className="muted">{notice}</p>}
        {(upload.error || update.error) && (
          <p role="alert" className="error">
            {(upload.error || update.error)?.message}
          </p>
        )}
      </form>
      <label className="show-completed">
        <input
          type="checkbox"
          checked={showArchived}
          onChange={(e) => setShowArchived(e.target.checked)}
        />
        Show archived
      </label>
      {assets.isPending && <div className="empty">Loading assets…</div>}
      {!assets.isPending && items.length === 0 && (
        <div className="empty">
          <h2>No shared assets yet</h2>
          <p>Upload a logo, intro sting, or reference image for this series.</p>
        </div>
      )}
      <div className="asset-grid">
        {items.map((asset) => (
          <article
            key={asset.id}
            className={asset.status === "archived" ? "asset archived" : "asset"}
          >
            <AssetPreview seriesId={seriesId} asset={asset} />
            <div className="asset-info">
              <strong title={asset.name ?? ""}>{asset.name}</strong>
              <small>
                {asset.kind} · {size(asset.byte_size)}
                {asset.provenance.origin === "promoted" && " · promoted"}
                {asset.status === "archived" && " · archived"}
              </small>
              <button
                className="secondary"
                disabled={update.isPending}
                onClick={() =>
                  update.mutate({
                    id: asset.id,
                    status: asset.status === "active" ? "archived" : "active",
                  })
                }
              >
                {asset.status === "active" ? (
                  <>
                    <Archive size={13} /> Archive
                  </>
                ) : (
                  <>
                    <RotateCcw size={13} /> Restore
                  </>
                )}
              </button>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function AssetPreview({
  seriesId,
  asset,
}: {
  seriesId: string;
  asset: SeriesAsset;
}) {
  const url = assetUrl(seriesId, asset.id);
  if (asset.content_type.startsWith("image/"))
    return <img className="asset-preview" src={url} alt={asset.name ?? ""} />;
  if (asset.content_type.startsWith("audio/"))
    return (
      <div className="asset-preview media">
        <audio controls preload="none" src={url} />
      </div>
    );
  return (
    <div className="asset-preview media">
      <video controls preload="metadata" src={url} />
    </div>
  );
}
