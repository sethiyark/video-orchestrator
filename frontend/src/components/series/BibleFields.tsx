import { useState } from "react";
import type { ComponentName, SeriesBible } from "../../lib/api";

const COMPONENTS: ComponentName[] = [
  "DefinitionCard",
  "AnimatedFlowDiagram",
  "BulletReveal",
  "ImagePan",
  "SeriesAsset",
];

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
}: {
  draft: BibleDraft;
  onChange: (draft: BibleDraft) => void;
  idPrefix: string;
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
