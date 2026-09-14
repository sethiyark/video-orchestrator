// Frame-only timing keeps random-access rendering deterministic: every helper
// is a pure function of the frame, never of previous frames.
export const clamp = (value) => Math.max(0, Math.min(1, value));
export const ease = (value) => 1 - (1 - clamp(value)) ** 3;
export const easeInOut = (value) => {
  const v = clamp(value);
  return v < 0.5 ? 4 * v * v * v : 1 - (-2 * v + 2) ** 3 / 2;
};
export const lerp = (a, b, t) => a + (b - a) * clamp(t);

// Reveal item `index` of `count` across the first 65% of the scene so the
// viewer keeps the end of the scene for reading.
export const revealAt = (frame, frames, index, count) =>
  ease((frame - (index * frames * 0.65) / count) / Math.min(20, frames * 0.12));

// Frames two neighbouring scenes overlap while one hands over to the next.
export const OVERLAP = 10;
export const TRANSITIONS = ["dissolve", "slide", "wipe"];

// Which transition a scene enters with. Chapter openings always wipe so a
// chapter boundary reads differently from a cut inside a chapter.
export const pickTransition = (chapterIndex, sceneIndex, chapterStart) =>
  chapterStart
    ? "chapter"
    : TRANSITIONS[(chapterIndex * 7 + sceneIndex * 3) % TRANSITIONS.length];

// Entrance/exit progress for a scene rendered from 0..frames+OVERLAP frames.
export const handover = (frame, frames, last) => ({
  enter: easeInOut(frame / OVERLAP),
  exit: last ? 0 : easeInOut((frame - frames) / OVERLAP),
});

// Count-up for StatCounter: settles on `target` after 60% of the scene.
export const counter = (frame, frames, target) =>
  target * easeInOut(frame / Math.max(1, Math.min(frames * 0.6, 75)));

// Characters visible of a typed string that starts at `start` frames.
export const typewriter = (frame, start, length, perFrame = 1.6) =>
  Math.max(0, Math.min(length, Math.floor((frame - start) * perFrame)));

// Music gain under narration: how much of a window around `frame` is speech.
// Words are {from, frames}; the result is deterministic per frame.
export const speechDensity = (words, frame, window = 18) => {
  if (!words.length) return 0;
  const lo = frame - window;
  const hi = frame + window;
  let covered = 0;
  for (const word of words) {
    const start = Math.max(lo, word.from);
    const end = Math.min(hi, word.from + word.frames + 6);
    if (end > start) covered += end - start;
    if (word.from > hi) break;
  }
  return clamp(covered / (2 * window));
};

export const musicGain = (words, frame, total, loud = 0.42, quiet = 0.14) => {
  const fadeIn = clamp(frame / 60);
  const fadeOut = clamp((total - frame) / 60);
  return lerp(loud, quiet, speechDensity(words, frame)) * fadeIn * fadeOut;
};

// Current caption line: the words of `sceneIndex` grouped into lines of at
// most `perLine`, and which line/word is active at `frame`.
export const captionAt = (words, sceneIndex, frame, perLine = 8) => {
  const scoped = words.filter((word) => word.scene === sceneIndex);
  if (!scoped.length) return null;
  const lines = [];
  for (let i = 0; i < scoped.length; i += perLine) {
    lines.push(scoped.slice(i, i + perLine));
  }
  let active = 0;
  for (let i = 0; i < scoped.length; i++) {
    if (scoped[i].from <= frame) active = i;
  }
  const line = lines[Math.floor(active / perLine)];
  return { line, active: scoped[active] };
};
