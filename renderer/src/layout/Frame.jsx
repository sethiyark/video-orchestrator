import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";

// Ground of every scene: the scene's own image as a blurred, darkened plate
// with slow drift, a faint grid, an accent glow and a vignette.
export const Frame = ({ plate, accent, progress, theme, dim = 0.5, children }) => (
  <AbsoluteFill
    style={{
      background: theme.bg,
      color: theme.text,
      fontFamily: theme.sans,
      overflow: "hidden",
    }}
  >
    {plate && (
      <Img
        src={staticFile(plate)}
        style={{
          position: "absolute",
          inset: -80,
          width: "calc(100% + 160px)",
          height: "calc(100% + 160px)",
          objectFit: "cover",
          filter: `blur(22px) saturate(1.15) brightness(${1 - dim})`,
          transform: `scale(${1.04 + progress * 0.05}) translate(${(progress - 0.5) * -30}px, ${(progress - 0.5) * -14}px)`,
        }}
      />
    )}
    <AbsoluteFill
      style={{
        background: `linear-gradient(180deg, ${theme.bg}cc, ${theme.bg}66 40%, ${theme.bg}dd)`,
      }}
    />
    <AbsoluteFill
      style={{
        backgroundImage:
          "linear-gradient(#ffffff05 1px, transparent 1px), linear-gradient(90deg, #ffffff05 1px, transparent 1px)",
        backgroundSize: "72px 72px",
        transform: `translateY(${progress * 24}px) scale(1.06)`,
      }}
    />
    <div
      style={{
        position: "absolute",
        width: 1100,
        height: 1100,
        right: -420,
        top: -520,
        background: `radial-gradient(circle, ${accent}22, transparent 62%)`,
      }}
    />
    <AbsoluteFill
      style={{
        background:
          "radial-gradient(ellipse at center, transparent 55%, #03070f99 100%)",
      }}
    />
    {children}
  </AbsoluteFill>
);
