import React from "react";
import { Img, staticFile } from "remotion";

import { revealAt } from "../motion.mjs";
import { panelStyle } from "./shared.jsx";

export const Outro = ({ scene, accent, theme, frame, frames }) => {
  const p = scene.props;
  return (
    <div style={{ display: "flex", gap: 60, alignItems: "flex-start", paddingTop: 10 }}>
      <div style={{ flex: 1.2 }}>
        {p.takeaways.map((item, i) => {
          const amount = revealAt(frame, frames, i, p.takeaways.length + 1);
          return (
            <div
              key={i}
              style={panelStyle(theme, accent, {
                padding: "24px 32px",
                marginBottom: 18,
                display: "flex",
                gap: 26,
                alignItems: "center",
                opacity: amount,
                transform: `translateX(${(1 - amount) * -40}px)`,
              })}
            >
              <div style={{ width: 14, height: 14, borderRadius: 7, background: accent, flexShrink: 0 }} />
              <div style={{ fontSize: 34, lineHeight: 1.35, fontWeight: 500 }}>{item}</div>
            </div>
          );
        })}
        {p.next_topic && (
          <div
            style={{
              marginTop: 26,
              color: theme.muted,
              fontSize: 28,
              opacity: revealAt(frame, frames, p.takeaways.length, p.takeaways.length + 1),
            }}
          >
            Next: <span style={{ color: theme.text, fontWeight: 600 }}>{p.next_topic}</span>
          </div>
        )}
      </div>
      <div
        style={panelStyle(theme, accent, {
          width: 560,
          height: 420,
          display: "grid",
          placeItems: "center",
          overflow: "hidden",
          flexShrink: 0,
        })}
      >
        {theme.outro ? (
          <Img src={staticFile(theme.outro)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        ) : theme.logo ? (
          <Img src={staticFile(theme.logo)} style={{ width: "60%", height: "60%", objectFit: "contain" }} />
        ) : (
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 22, letterSpacing: 6, color: accent, fontWeight: 700 }}>THANKS FOR WATCHING</div>
            <div style={{ fontSize: 44, fontWeight: 800, marginTop: 16 }}>{theme.name}</div>
          </div>
        )}
      </div>
    </div>
  );
};
