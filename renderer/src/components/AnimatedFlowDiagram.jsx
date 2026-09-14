import React from "react";

import { revealAt } from "../motion.mjs";
import { panelStyle } from "./shared.jsx";

export const AnimatedFlowDiagram = ({ scene, accent, theme, frame, frames, index }) => {
  const p = scene.props;
  const count = p.nodes.length;
  const columns = count <= 4 ? count : Math.ceil(count / 2);
  const width = 1640 / columns;
  const rows = Math.ceil(count / columns);
  const position = (i) => {
    const row = Math.floor(i / columns);
    const col = row % 2 ? columns - 1 - (i % columns) : i % columns;
    return { x: col * width + width / 2, y: rows === 1 ? 285 : 160 + row * 300 };
  };
  const reveal = (i) => revealAt(frame, frames, i, count);
  return (
    <div style={{ position: "relative", height: 610 }}>
      <svg width="1640" height="610" style={{ position: "absolute", inset: 0 }}>
        <defs>
          <marker id={`arrow-${index}`} markerWidth="10" markerHeight="10" refX="8" refY="4" orient="auto">
            <path d="M0,0 L8,4 L0,8" fill="none" stroke={accent} strokeWidth="1.5" />
          </marker>
        </defs>
        {p.nodes.slice(1).map((_, j) => {
          const a = position(j);
          const b = position(j + 1);
          const vertical = a.x === b.x;
          const direction = Math.sign(b.x - a.x);
          const x1 = a.x + (vertical ? 0 : direction * (width / 2 - 34));
          const x2 = b.x - (vertical ? 0 : direction * (width / 2 - 34));
          const y1 = a.y + (vertical ? 85 : 0);
          const y2 = b.y - (vertical ? 85 : 0);
          const amount = reveal(j + 1);
          const travel = (frame % 65) / 65;
          return (
            <g key={j} opacity={amount}>
              <path
                d={`M${x1},${y1} L${x2},${y2}`}
                stroke={accent}
                strokeWidth="3"
                fill="none"
                pathLength="1"
                strokeDasharray="1"
                strokeDashoffset={1 - amount}
                markerEnd={`url(#arrow-${index})`}
              />
              <circle cx={x1 + (x2 - x1) * travel} cy={y1 + (y2 - y1) * travel} r="5" fill="#fff" />
            </g>
          );
        })}
      </svg>
      {p.nodes.map((node, i) => {
        const pos = position(i);
        const amount = reveal(i);
        return (
          <div
            key={i}
            style={panelStyle(theme, accent, {
              position: "absolute",
              left: pos.x - width / 2 + 34,
              top: pos.y - 85,
              width: width - 68,
              minHeight: 170,
              boxSizing: "border-box",
              padding: "22px 24px",
              opacity: amount,
              transform: `translateY(${(1 - amount) * 28}px)`,
              borderTop: `3px solid ${accent}`,
            })}
          >
            <div style={{ color: accent, fontSize: 19, marginBottom: 14, letterSpacing: 3, fontWeight: 700 }}>
              STEP {String(i + 1).padStart(2, "0")}
            </div>
            <div style={{ fontSize: node.length > 65 ? 25 : 32, lineHeight: 1.25, fontWeight: 500 }}>{node}</div>
          </div>
        );
      })}
    </div>
  );
};
