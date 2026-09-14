# Rendering

Sources: `backend/app/rendering.py`, `renderer/`, `backend/app/render_sample.py`.

## Responsibility

Render the closed storyboard schema into a real 1920×1080, 30 fps H.264/AAC
MP4. Remotion renders fixed React components and its bundled FFmpeg encodes
and muxes the narration. No system FFmpeg installation is needed.

## Public surface

`RemotionRenderer.render(job, artifacts, library)` returns `video` (a
content-addressed MP4 descriptor), duration, dimensions, codecs, the frame
`timeline`, the positioned `chapters`, and the `captions`/`music`/
`intro_frames` it rendered with. `timeline(scenes, alignment, duration)`
builds contiguous scenes from aligned word starts; `word_timeline(...)` builds
the caption words (`{text, from, frames, scene}`); both share `timed_words`.
Segment-only alignment interpolates word starts within each segment. WAV
duration determines the final frame, preserving leading silence and the audio
tail. Token sequences must match the storyboard; missing, non-finite,
overlapping or out-of-range timestamps fail closed. `font_sources()` lists
the vendored font files (`FONT_FILES`) under the renderer's installed
`@fontsource` packages.

## How it is called

Run `make setup-renderer` once (Node >=22.12 and pnpm required). This installs
locked packages (Remotion, React, `@fontsource/inter`,
`@fontsource/jetbrains-mono`) and Chrome Headless Shell. `LocalProvider` calls
the renderer at the existing render stage; `RenderError` becomes
`IntegrationUnavailable`. The provider validates alignment before rendering and
can rewind invalid saved alignment to alignment or narration under the
existing Governor budget. No model or GPU inference is launched by the renderer
itself. `make render-sample` produces a two-minute, three-chapter sample that
uses all fourteen components over gradient plates (a zlib-only PNG writer) and
a quiet calibration tone (not synthesized speech), under
`backend/data/artifacts/render-sample`.

The Node entry point takes three internal filesystem arguments: JSON manifest,
staged media directory, output MP4. It bundles only the checked-in composition.
Browser downloads are disabled during rendering; setup owns the download.
[Remotion renderMedia documentation](https://www.remotion.dev/docs/renderer/render-media).

### Manifest

`render()` stages every input next to the media and writes one `props.json`:

- `scenes[]`: the storyboard scenes with `from`/`frames`, the `chapter`
  index, and `plate` — the scene's own image from `assets.images` (matched by
  `id`, or legacy `scene_id`) or, when the scene has none (budget fallback
  or an image-less storyboard), the chapter hero. `ImagePan` uses the plate as
  its subject and fails without one; `SeriesAsset` stages the pinned library
  file after re-hashing it.
- `chapters[]`: `chapter_id`, title, tagline, accent, `index`, `from`,
  `frames` (sum of its scenes) and the hero `image`. A storyboard planned
  before chapters existed renders as one chapter titled after the job.
- `words[]`: caption words from `word_timeline`.
- `brand`: the series name and palette from the job's series snapshot plus
  `logo`/`intro`/`outro` files from the pinned `assets.brand`; `music`: the
  pinned music bed file or `null`; `captions` from the job's render options
  (default true); `introFrames` (`INTRO_FRAMES`, 75) when the brand has a
  logo or intro plate — every scene, chapter and word shifts by that much and
  the narration starts after it.
- `fonts/`: the vendored woff2 files, copied from the renderer's
  `node_modules`, so Chrome loads them from the loopback asset server.

## Visual presentation

`renderer/src/` is a small component library:

| Module | Role |
| --- | --- |
| `index.jsx` | Composition root: sequences per scene with `OVERLAP` frames, brand intro, overlay (captions + rail), narration and looped music with a per-frame gain |
| `theme.mjs` | Palette (series bible palette when it has ≥3 colours, else 12 defaults), fonts, colours; `FONT_FILES` |
| `fonts.mjs` | Injects `@font-face` rules for the staged fonts and waits a bounded time for them (`useFonts`); a missing file falls back to the CSS stack, never stalls the render |
| `motion.mjs` | Pure frame functions: `revealAt`, `handover` (enter/exit over `OVERLAP`), `pickTransition` (chapter openings wipe; other cuts pick dissolve/slide/wipe deterministically), `counter`, `typewriter`, `captionAt`, `speechDensity`/`musicGain` |
| `highlight.mjs` | Display-only tokenizer (keyword/string/comment/number/punctuation) for the `CodeBlock` language enum; nothing is evaluated |
| `icons.jsx` | The closed `IconGrid` icon set as inline SVG paths |
| `layout/` | `Frame` (blurred, darkened plate with drift, grid, glow, vignette), `Header` (brand name, logo watermark, chapter label, scene counter), `Rail` (chapter-segmented progress bar), `Captions` (karaoke line with the active word highlighted), `Opener` (72-frame chapter title overlay on a chapter's first scene when it is not a `ChapterTitle`) |
| `components/` | One file per storyboard component; `index.mjs` is the registry and `FULL_FRAME` lists the ones that own the whole frame |

Components: `DefinitionCard` (decorative rings + card), `AnimatedFlowDiagram`
(snake layout, drawn arrows, travelling dots), `BulletReveal`, `ImagePan`
(slow push-in), `SeriesAsset` (framing preserved, caption gradient),
`ChapterTitle` (full-frame hero with chapter number), `Outro` (staggered
takeaways, next topic, outro plate/logo/brand card), `CodeBlock` (window
chrome, line numbers, highlighted lines, per-line reveal), `Terminal` (typed
commands, output after each command), `Comparison` (two columns, VS badge),
`StatCounter` (count-up on the leading number of each value), `Timeline`
(alternating cards on a drawn line), `Callout` (pull-quote with the claim
id), `IconGrid` (icon tiles). Reveals follow scene duration, not spoken
words, leaving the last third of a scene for reading. Every scene sits on its
plate; text is escaped React content. All motion is deterministic from the
video frame; no remote assets are needed. Existing MP4s must be rendered again
to receive this presentation.

## Invariants

- Only the fourteen components above are supported (the same closed enum as
  `schemas.COMPONENTS`). Text, code and terminal lines are displayed, never
  executed. Icons and code languages are closed enums.
- Images are copied from resolved job artifacts (generated, cached, or
  uploaded through the image relay) or hash-verified pinned series media;
  model-supplied URLs and paths never become image sources. Brand plates and
  the music bed are pinned series assets verified the same way.
- Fonts come from the renderer's installed packages; the composition never
  loads a font, image or script from the network.
- The renderer asset server binds to loopback only.
- Node receives only PATH, HOME, TMPDIR and SYSTEMROOT from the environment.
- Failed renders do not adopt an MP4. Temporary media and bundles are removed.
- Cancellation and the two-hour timeout kill the render process group.
- Upload remains unavailable and retains the approval gate.

## Related tests

`backend/tests/test_rendering.py`: timing, invalid input, missing images,
process failure, artifact adoption, secret stripping, the manifest
(`test_word_timeline_and_manifest_carry_chapters_plates_and_captions`),
`motion.mjs`/`highlight.mjs` helpers in Node without Chrome
(`test_renderer_motion_and_highlight_helpers_are_deterministic`), and
`test_real_render_covers_every_component`, a ~14 s real Remotion/Chrome
render of all components that skips when `make setup-renderer` has not run.
The default tests use fake subprocesses and never download Chrome, models or
media.

## Known limitations

No thumbnail generation, automated visual QC or YouTube adapter. Segment-only
word timing is approximate, so captions from segment-only alignment drift
within a segment. The fixed layout is intended for concise scene text; very
dense content may exceed the available space. Rendering runs on the local
host; the existing Compose image does not install the Node renderer or
Chrome. Package and browser setup need network access. Transitions overlap
scenes by 10 frames, so a scene shorter than that shows no handover.
