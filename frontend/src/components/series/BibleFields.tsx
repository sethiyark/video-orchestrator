import { useState } from "react";
import {
  COMPONENT_NAMES,
  type ComponentName,
  type SeriesAsset,
  type SeriesBible,
} from "../../lib/api";

const COMPONENTS: readonly ComponentName[] = COMPONENT_NAMES;
/** Brand-kit slots → the library asset kinds they accept. */
const BRAND_SLOTS: { key: BrandKey; label: string; kinds: string[] }[] = [
  { key: "logoAssetId", label: "Logo", kinds: ["logo", "image"] },
  { key: "introAssetId", label: "Intro plate", kinds: ["logo", "image"] },
  { key: "outroAssetId", label: "Outro plate", kinds: ["logo", "image"] },
  { key: "musicAssetId", label: "Music bed", kinds: ["music", "audio"] },
];
type BrandKey = "logoAssetId" | "introAssetId" | "outroAssetId" | "musicAssetId";

const lines = (text: string) =>
  text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

export type BibleDraft = {
  audience: string;
  tone: string;
  styleRules: string;
  avoidPhrases: string;
  palette: string;
  components: ComponentName[];
  imageStyle: string;
  logoAssetId: string;
  introAssetId: string;
  outroAssetId: string;
  musicAssetId: string;
  glossary: string;
};

export const toDraft = (bible: SeriesBible): BibleDraft => ({
  audience: bible.voice.audience,
  tone: bible.voice.tone,
  styleRules: bible.voice.style_rules.join("\n"),
  avoidPhrases: bible.voice.avoid_phrases.join("\n"),
  palette: bible.visual.palette.join(", "),
  components: bible.visual.preferred_components,
  imageStyle: bible.visual.image_style,
  logoAssetId: bible.visual.logo_asset_id ?? "",
  introAssetId: bible.visual.intro_asset_id ?? "",
  outroAssetId: bible.visual.outro_asset_id ?? "",
  musicAssetId: bible.visual.music_asset_id ?? "",
  glossary: bible.glossary
    .map((entry) => `${entry.term}: ${entry.definition}`)
    .join("\n"),
});

export const fromDraft = (draft: BibleDraft): SeriesBible => ({
  voice: {
    audience: draft.audience.trim(),
    tone: draft.tone.trim(),
    style_rules: lines(draft.styleRules),
    avoid_phrases: lines(draft.avoidPhrases),
  },
  visual: {
    palette: draft.palette
      .split(/[\s,]+/)
      .map((color) => color.trim())
      .filter(Boolean),
    preferred_components: draft.components,
    image_style: draft.imageStyle.trim(),
    logo_asset_id: draft.logoAssetId || null,
    intro_asset_id: draft.introAssetId || null,
    outro_asset_id: draft.outroAssetId || null,
    music_asset_id: draft.musicAssetId || null,
  },
  glossary: lines(draft.glossary).map((line) => {
    const split = line.indexOf(":");
    return split < 0
      ? { term: line, definition: "" }
      : {
          term: line.slice(0, split).trim(),
          definition: line.slice(split + 1).trim(),
        };
  }),
});

export function useBibleDraft(bible: SeriesBible) {
  return useState<BibleDraft>(() => toDraft(bible));
}

/** Voice, visual, and glossary inputs. Style guidance only — never evidence. */
export function BibleFields({
  draft,
  onChange,
  idPrefix,
  assets,
}: {
  draft: BibleDraft;
  onChange: (draft: BibleDraft) => void;
  idPrefix: string;
  /** Active series library assets for the brand-kit pickers; omit to hide them. */
  assets?: SeriesAsset[];
}) {
  const set = <K extends keyof BibleDraft>(key: K, value: BibleDraft[K]) =>
    onChange({ ...draft, [key]: value });
  const id = (name: string) => `${idPrefix}-${name}`;
  const swatches = draft.palette
    .split(/[\s,]+/)
    .filter((color) => /^#[0-9a-fA-F]{6}$/.test(color));
  return (
    <>
      <fieldset className="bible-group">
        <legend>Voice &amp; tone</legend>
        <label htmlFor={id("audience")}>Audience</label>
        <input
          id={id("audience")}
          maxLength={300}
          value={draft.audience}
          onChange={(e) => set("audience", e.target.value)}
          placeholder="Working backend engineers"
        />
        <label htmlFor={id("tone")}>Tone</label>
        <input
          id={id("tone")}
          maxLength={300}
          value={draft.tone}
          onChange={(e) => set("tone", e.target.value)}
          placeholder="Calm, precise, lightly dry humour"
        />
        <label htmlFor={id("rules")}>
          Style rules <span>(one per line)</span>
        </label>
        <textarea
          id={id("rules")}
          rows={4}
          value={draft.styleRules}
          onChange={(e) => set("styleRules", e.target.value)}
          placeholder={"Open with the failure mode\nPrefer concrete numbers"}
        />
        <label htmlFor={id("avoid")}>
          Phrases to avoid <span>(one per line)</span>
        </label>
        <textarea
          id={id("avoid")}
          rows={3}
          value={draft.avoidPhrases}
          onChange={(e) => set("avoidPhrases", e.target.value)}
          placeholder={"In today's video\nSmash that like button"}
        />
      </fieldset>
      <fieldset className="bible-group">
        <legend>Visual style</legend>
        <label htmlFor={id("palette")}>
          Palette <span>(hex, comma separated)</span>
        </label>
        <input
          id={id("palette")}
          value={draft.palette}
          onChange={(e) => set("palette", e.target.value)}
          placeholder="#23362d, #409b76, #f8f9f6"
        />
        {swatches.length > 0 && (
          <div className="swatches" aria-hidden="true">
            {swatches.map((color, index) => (
              <span key={`${color}-${index}`} style={{ background: color }} />
            ))}
          </div>
        )}
        <div className="field-label">Preferred scene components</div>
        <div className="checks">
          {COMPONENTS.map((name) => (
            <label key={name} className="check">
              <input
                type="checkbox"
                checked={draft.components.includes(name)}
                onChange={(e) =>
                  set(
                    "components",
                    e.target.checked
                      ? [...draft.components, name]
                      : draft.components.filter((item) => item !== name),
                  )
                }
              />
              {name}
            </label>
          ))}
        </div>
        <label htmlFor={id("image-style")}>Image style</label>
        <input
          id={id("image-style")}
          maxLength={300}
          value={draft.imageStyle}
          onChange={(e) => set("imageStyle", e.target.value)}
          placeholder="Flat vector, muted greens, no text"
        />
      </fieldset>
      {assets && (
        <fieldset className="bible-group">
          <legend>Brand kit</legend>
          <p className="muted">
            Library assets every video in this series reuses: a logo watermark,
            intro and outro plates, and a music bed ducked under narration.
          </p>
          {BRAND_SLOTS.map((slot) => {
            const options = assets.filter(
              (asset) => asset.status === "active" && slot.kinds.includes(asset.kind),
            );
            return (
              <div key={slot.key}>
                <label htmlFor={id(slot.key)}>{slot.label}</label>
                <select
                  id={id(slot.key)}
                  value={draft[slot.key]}
                  onChange={(e) => set(slot.key, e.target.value)}
                >
                  <option value="">None</option>
                  {options.map((asset) => (
                    <option key={asset.id} value={asset.id}>
                      {asset.name || asset.id} · {asset.kind}
                    </option>
                  ))}
                </select>
              </div>
            );
          })}
        </fieldset>
      )}
      <fieldset className="bible-group">
        <legend>Glossary</legend>
        <label htmlFor={id("glossary")}>
          Terms <span>(one per line, “Term: definition”)</span>
        </label>
        <textarea
          id={id("glossary")}
          rows={5}
          value={draft.glossary}
          onChange={(e) => set("glossary", e.target.value)}
          placeholder={"Resolver: The server that answers DNS queries"}
        />
        <p className="muted">
          Glossary wording guides phrasing only. It is never treated as evidence
          for a claim.
        </p>
      </fieldset>
    </>
  );
}
