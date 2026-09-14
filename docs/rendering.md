# Rendering

Sources: `backend/app/rendering.py`, `renderer/`, `backend/app/render_sample.py`.

## Responsibility

Render the closed storyboard schema into a real 1920×1080, 30 fps H.264/AAC
MP4. Remotion renders fixed React components and its bundled FFmpeg encodes
and muxes the narration. No system FFmpeg installation is needed.

## Public surface

`RemotionRenderer.render(job, artifacts, library)` returns `video` (a
content-addressed MP4 descriptor), duration, dimensions, codecs and the frame
timeline. `timeline(scenes, alignment, duration)` builds contiguous scenes
from aligned word starts. Segment-only alignment interpolates word starts
within each segment. WAV duration determines the final frame, preserving
leading silence and the audio tail. Token sequences must match the storyboard;
missing, non-finite, overlapping or out-of-range timestamps fail closed.

## How it is called

Run `make setup-renderer` once (Node >=22.12 and pnpm required). This installs
locked packages and Chrome Headless Shell. `LocalProvider` calls the renderer
at the existing render stage; `RenderError` becomes `IntegrationUnavailable`.
The provider validates alignment before rendering and can rewind invalid saved
alignment to alignment or narration under the existing Governor budget. The
alignment stage may use validated TTS sentence timing after fidelity passes.
No model or GPU inference is launched by the renderer itself. `make render-sample`
produces a two-minute programmatic sample with a quiet calibration tone
(not synthesized speech), under `backend/data/artifacts/render-sample`.

The Node entry point takes three internal filesystem arguments: JSON manifest,
staged media directory, output MP4. It bundles only the checked-in composition.
Browser downloads are disabled during rendering; setup owns the download.
[Remotion renderMedia documentation](https://www.remotion.dev/docs/renderer/render-media).

## Invariants

- Only DefinitionCard, AnimatedFlowDiagram, BulletReveal, ImagePan and
  SeriesAsset are supported. Text is escaped React content, never code or HTML.
- Images are copied from resolved job artifacts or hash-verified pinned series
  media; model-supplied URLs and paths never become image sources.
- The renderer asset server binds to loopback only.
- Node receives only PATH, HOME, TMPDIR and SYSTEMROOT from the environment.
- Failed renders do not adopt an MP4. Temporary media and bundles are removed.
- Cancellation and the two-hour timeout kill the render process group.
- Upload remains unavailable and retains the approval gate.

## Related tests

`backend/tests/test_rendering.py`: timing, invalid input, missing images,
process failure, artifact adoption and secret stripping. The default tests use
fake subprocesses and never download Chrome, models or media.

## Known limitations

No captions, music mix, thumbnail generation, automated visual QC or YouTube
adapter. Segment-only word timing is approximate. The fixed layout is intended
for concise scene text; very dense content may exceed the available space.
Rendering runs on the local host; the existing Compose image does not install
the Node renderer or Chrome. Package and browser setup need network access.
