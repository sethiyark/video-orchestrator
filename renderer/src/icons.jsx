import React from "react";

// Closed icon set drawn as inline stroke paths (viewBox 0 0 24 24). The
// storyboard schema only admits these names; nothing is fetched.
const PATHS = {
  server: "M4 5h16v5H4zM4 14h16v5H4zM7 7.5h.01M7 16.5h.01",
  database: "M12 4c4.4 0 8 1.3 8 3s-3.6 3-8 3-8-1.3-8-3 3.6-3 8-3zM4 7v10c0 1.7 3.6 3 8 3s8-1.3 8-3V7M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3",
  cloud: "M7 18h10a4 4 0 0 0 .5-8A6 6 0 0 0 6 11a3.5 3.5 0 0 0 1 7z",
  lock: "M6 11h12v9H6zM9 11V7a3 3 0 0 1 6 0v4M12 15v2",
  key: "M14 4a5 5 0 1 0 2.3 9.4L20 17v3h-3v-2h-2v-2l-1.6-1.6A5 5 0 0 0 14 4z",
  network: "M12 3v5M12 8a3 3 0 1 0 0 .1M5 21v-4a3 3 0 1 0 0-.1M19 21v-4a3 3 0 1 0 0-.1M12 11l-7 6M12 11l7 6",
  cpu: "M7 7h10v10H7zM10 10h4v4h-4zM9 3v4M15 3v4M9 17v4M15 17v4M3 9h4M3 15h4M17 9h4M17 15h4",
  memory: "M3 8h18v8H3zM7 8v8M11 8v8M15 8v8M5 16v2M9 16v2M13 16v2M17 16v2",
  disk: "M4 4h13l3 3v13H4zM8 4v5h7V4M8 20v-6h8v6",
  code: "M8 8l-4 4 4 4M16 8l4 4-4 4M14 5l-4 14",
  terminal: "M3 5h18v14H3zM7 9l3 3-3 3M12 15h5",
  browser: "M3 5h18v14H3zM3 9h18M6 7h.01M9 7h.01",
  mobile: "M8 3h8v18H8zM11 18h2",
  user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0",
  users: "M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM2 20a7 7 0 0 1 14 0M16 4a3.5 3.5 0 0 1 0 7M22 20a7 7 0 0 0-5-6.7",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 2",
  bolt: "M13 2L4 14h7l-1 8 9-12h-7z",
  shield: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6zM9 12l2 2 4-4",
  gear: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2",
  chart: "M4 20V4M4 20h16M8 16v-5M12 16V8M16 16v-3M20 16V6",
  search: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM16 16l5 5",
  mail: "M3 6h18v12H3zM3 7l9 6 9-6",
  globe: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18",
  warning: "M12 3l10 18H2zM12 10v5M12 18h.01",
};

export const ICONS = Object.keys(PATHS);

export const Icon = ({ name, size = 64, color = "#fff", strokeWidth = 1.6 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <path
      d={PATHS[name] || PATHS.warning}
      stroke={color}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);
