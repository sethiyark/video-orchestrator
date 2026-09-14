import React from "react";
import { Img, staticFile } from "remotion";

import { panelStyle } from "./shared.jsx";

// ImagePan shows the image as the subject; SeriesAsset preserves its framing.
export const ImagePan = ({ scene, accent, theme, progress }) => {
  const pan = scene.component === "ImagePan";
  const caption = scene.props.caption;
  return (
    <div style={panelStyle(theme, accent, { position: "relative", height: 620, overflow: "hidden" })}>
      <Img
        src={staticFile(scene.image)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: pan ? "cover" : "contain",
          transform: pan
            ? `scale(${1.04 + progress * 0.08}) translateX(${(progress - 0.5) * 24}px)`
            : undefined,
        }}
      />
      {caption && (
        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            right: 0,
            padding: "46px 36px 26px",
            background: "linear-gradient(transparent, #07101fee)",
            fontSize: 30,
            fontWeight: 500,
          }}
        >
          {caption}
        </div>
      )}
    </div>
  );
};

export const SeriesAsset = ImagePan;
