// Visual tokens shared by every component; the series brand kit overrides the
// palette and name, everything else stays fixed so videos look like a family.
export const DEFAULT_PALETTE = [
  "#5eead4",
  "#a5b4fc",
  "#fbbf24",
  "#f472b6",
  "#86efac",
  "#fca5a5",
  "#7dd3fc",
  "#fde68a",
  "#c4b5fd",
  "#6ee7b7",
  "#fdba74",
  "#93c5fd",
];

export const buildTheme = (brand = {}) => {
  const palette =
    brand.palette && brand.palette.length >= 3 ? brand.palette : DEFAULT_PALETTE;
  return {
    palette,
    accent: (index) => palette[((index % palette.length) + palette.length) % palette.length],
    name: (brand.name || "Engineering Explained").toUpperCase(),
    logo: brand.logo || null,
    intro: brand.intro || null,
    outro: brand.outro || null,
    bg: "#07101f",
    panel: "#111f32cc",
    line: "#ffffff20",
    text: "#edf3fc",
    muted: "#9fb0c8",
    sans: "Inter, Arial, Helvetica, sans-serif",
    mono: '"JetBrains Mono", Menlo, Consolas, monospace',
  };
};

// Font files rendering.py copies next to the media (from @fontsource).
export const FONT_FILES = [
  ["Inter", "400", "inter-latin-400-normal.woff2"],
  ["Inter", "500", "inter-latin-500-normal.woff2"],
  ["Inter", "600", "inter-latin-600-normal.woff2"],
  ["Inter", "700", "inter-latin-700-normal.woff2"],
  ["Inter", "800", "inter-latin-800-normal.woff2"],
  ["JetBrains Mono", "400", "jetbrains-mono-latin-400-normal.woff2"],
  ["JetBrains Mono", "600", "jetbrains-mono-latin-600-normal.woff2"],
];
