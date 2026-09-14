import React from "react";
import {
  AbsoluteFill,
  Audio,
  Composition,
  Img,
  Sequence,
  interpolate,
  registerRoot,
  staticFile,
  useCurrentFrame,
} from "remotion";

const Scene = ({ scene }) => {
  const frame = useCurrentFrame();
  const p = scene.props;
  const opacity = interpolate(frame, [0, 12], [0, 1], {
    extrapolateRight: "clamp",
  });
  let content;
  switch (scene.component) {
    case "DefinitionCard":
      content = <p style={{ fontSize: 48, lineHeight: 1.4 }}>{p.body}</p>;
      break;
    case "AnimatedFlowDiagram":
      content = (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 24 }}>
          {p.nodes.map((node, i) => (
            <div
              key={i}
              style={{
                padding: 24,
                border: "2px solid #67e8f9",
                borderRadius: 18,
                opacity: frame >= i * 8 ? 1 : 0,
                fontSize: 32,
                maxWidth: 340,
              }}
            >
              {i + 1}. {node}
            </div>
          ))}
        </div>
      );
      break;
    case "BulletReveal":
      content = (
        <ul style={{ fontSize: 40, lineHeight: 1.6 }}>
          {p.bullets.map((bullet, i) => (
            <li
              key={i}
              style={{
                opacity:
                  frame >= i * Math.min(20, scene.frames / p.bullets.length)
                    ? 1
                    : 0,
              }}
            >
              {bullet}
            </li>
          ))}
        </ul>
      );
      break;
    case "ImagePan":
    case "SeriesAsset":
      content = (
        <>
          <Img
            src={staticFile(scene.image)}
            style={{
              height: 600,
              width: "100%",
              objectFit: "contain",
              transform:
                scene.component === "ImagePan"
                  ? `scale(${1 + (frame / scene.frames) * 0.04})`
                  : undefined,
            }}
          />
          {p.caption && <p style={{ fontSize: 30 }}>{p.caption}</p>}
        </>
      );
      break;
    default:
      throw new Error("Unsupported scene component");
  }
  return (
    <AbsoluteFill
      style={{
        background: "#0b1220",
        color: "#e2e8f0",
        padding: "70px 100px",
        fontFamily: "Arial, sans-serif",
      }}
    >
      <div style={{ opacity, overflow: "hidden", overflowWrap: "anywhere" }}>
        <div style={{ fontSize: 22, color: "#67e8f9", letterSpacing: 5 }}>
          ENGINEERING EXPLAINED
        </div>
        <h1 style={{ fontSize: 64, margin: "24px 0 38px" }}>{p.title}</h1>
        {content}
      </div>
    </AbsoluteFill>
  );
};
const Video = ({ scenes, audio }) => (
  <AbsoluteFill>
    {scenes.map((scene) => (
      <Sequence
        key={scene.scene_id}
        from={scene.from}
        durationInFrames={scene.frames}
      >
        <Scene scene={scene} />
      </Sequence>
    ))}
    <Audio src={staticFile(audio)} />
  </AbsoluteFill>
);
registerRoot(() => (
  <Composition
    id="Explainer"
    component={Video}
    width={1920}
    height={1080}
    fps={30}
    durationInFrames={30}
    defaultProps={{ scenes: [], audio: "narration.wav" }}
    calculateMetadata={({ props }) => ({
      durationInFrames: props.durationInFrames,
    })}
  />
));
