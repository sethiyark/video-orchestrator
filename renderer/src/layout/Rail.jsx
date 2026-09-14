import React from "react";

// Chapter-segmented progress rail; segment widths follow chapter durations.
export const Rail = ({ chapters, frame, theme }) => (
  <div
    style={{
      position: "absolute",
      left: 140,
      right: 140,
      bottom: 44,
      display: "flex",
      gap: 8,
    }}
  >
    {chapters.map((chapter, i) => {
      const done = frame >= chapter.from + chapter.frames;
      const inside = frame >= chapter.from && !done;
      const fill = done ? 1 : inside ? (frame - chapter.from) / chapter.frames : 0;
      return (
        <div
          key={chapter.chapter_id}
          style={{
            flex: Math.max(1, chapter.frames),
            height: inside ? 6 : 4,
            marginTop: inside ? 0 : 1,
            background: "#ffffff18",
            borderRadius: 4,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              width: `${fill * 100}%`,
              height: "100%",
              background: theme.accent(chapter.accent ?? i),
            }}
          />
        </div>
      );
    })}
  </div>
);
