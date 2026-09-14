import React from "react";

export const panelStyle = (theme, accent, extra = {}) => ({
  background: theme.panel,
  border: `1px solid ${theme.line}`,
  borderRadius: 24,
  backdropFilter: "blur(6px)",
  boxShadow: "0 24px 60px #00000055",
  ...extra,
});

export const Eyebrow = ({ children, accent, style }) => (
  <div
    style={{
      color: accent,
      fontSize: 20,
      letterSpacing: 4,
      fontWeight: 700,
      ...style,
    }}
  >
    {children}
  </div>
);

export const Title = ({ children, entrance, size }) => (
  <h1
    style={{
      fontSize: size || (children.length > 65 ? 50 : 64),
      lineHeight: 1.12,
      margin: "26px 0 22px",
      maxWidth: 1550,
      fontWeight: 800,
      letterSpacing: -0.5,
      opacity: entrance,
      transform: `translateY(${(1 - entrance) * 18}px)`,
    }}
  >
    {children}
  </h1>
);

export const fit = (text, large, small, limit) => (text.length > limit ? small : large);
