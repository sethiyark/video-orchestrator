import React from "react";

import { revealAt } from "../motion.mjs";
import { panelStyle } from "./shared.jsx";

export const Timeline = ({ scene, accent, theme, frame, frames }) => {
  const events = scene.props.events;
  const step = 1640 / events.length;
  const drawn = revealAt(frame, frames, events.length - 1, events.length);
  return (
    <div style={{ position: "relative", height: 580 }}>
      <div style={{ position: "absolute", left: step / 2, right: step / 2, top: 290, height: 4, background: "#ffffff22" }} />
      <div style={{ position: "absolute", left: step / 2, width: `${drawn * (1640 - step)}px`, top: 290, height: 4, background: accent }} />
      {events.map((event, i) => {
        const amount = revealAt(frame, frames, i, events.length);
        const above = i % 2 === 0;
        return (
          <div key={i} style={{ position: "absolute", left: i * step, width: step, top: 0, height: 580 }}>
            <div
              style={{
                position: "absolute",
                left: step / 2 - 16,
                top: 276,
                width: 32,
                height: 32,
                borderRadius: 16,
                background: theme.bg,
                border: `4px solid ${accent}`,
                transform: `scale(${amount})`,
              }}
            />
            <div
              style={panelStyle(theme, accent, {
                position: "absolute",
                left: 12,
                right: 12,
                [above ? "bottom" : "top"]: 330,
                padding: "18px 20px",
                opacity: amount,
                transform: `translateY(${(1 - amount) * (above ? 20 : -20)}px)`,
              })}
            >
              <div style={{ color: accent, fontSize: 22, fontWeight: 700, letterSpacing: 2 }}>{event.label}</div>
              {event.text && <div style={{ fontSize: 24, marginTop: 10, lineHeight: 1.3, fontWeight: 500 }}>{event.text}</div>}
            </div>
          </div>
        );
      })}
    </div>
  );
};
