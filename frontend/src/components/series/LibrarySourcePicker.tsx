import { useQuery } from "@tanstack/react-query";
import { api, type LibrarySource } from "../../lib/api";

/** Checkbox list of a series' reusable excerpts, for job creation forms. */
export function LibrarySourcePicker({
  seriesId,
  selected,
  onChange,
}: {
  seriesId: string;
  selected: string[];
  onChange: (ids: string[]) => void;
}) {
  const sources = useQuery({
    queryKey: ["series", seriesId, "sources"],
    queryFn: () => api<LibrarySource[]>(`/series/${seriesId}/sources`),
  });
  if (!sources.data?.length) return null;
  return (
    <>
      <div className="field-label">
        Library sources <span>(copied into the video)</span>
      </div>
      <div className="source-picks">
        {sources.data.map((source) => (
          <label key={source.id} className="check">
            <input
              type="checkbox"
              checked={selected.includes(source.id)}
              onChange={(e) =>
                onChange(
                  e.target.checked
                    ? [...selected, source.id]
                    : selected.filter((id) => id !== source.id),
                )
              }
            />
            <span>
              {source.title} <small>({source.source_key})</small>
            </span>
          </label>
        ))}
      </div>
    </>
  );
}
