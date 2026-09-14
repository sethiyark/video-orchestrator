import React from "react";
import { Img, staticFile } from "remotion";

export const Header = ({ theme, accent, chapter, index, total, entrance }) => (
  <div
    style={{
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
      fontSize: 20,
      color: accent,
      letterSpacing: 4,
      fontWeight: 600,
      opacity: entrance,
    }}
  >
    <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
      {theme.logo && (
        <Img
          src={staticFile(theme.logo)}
          style={{ height: 34, width: "auto", maxWidth: 140, objectFit: "contain" }}
        />
      )}
      <span>{theme.name}</span>
      {chapter && (
        <span style={{ color: theme.muted, letterSpacing: 2, fontWeight: 500 }}>
          · CH {String(chapter.index + 1).padStart(2, "0")} — {chapter.title.toUpperCase()}
        </span>
      )}
    </div>
    <span style={{ color: theme.muted }}>
      {String(index + 1).padStart(2, "0")} / {String(total).padStart(2, "0")}
    </span>
  </div>
);
